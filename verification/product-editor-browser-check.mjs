// Run from the disposable directory created by product-editor-browser-seed.py.
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
const {chromium}=await import(process.env.PLAYWRIGHT_MODULE || 'playwright');
const origin=process.env.PRODUCT_TEST_ORIGIN || 'http://127.0.0.1:18767';
const pid='proj_67916afd', sid='setup_products_fixture';
const {sku,name}=JSON.parse(await readFile('fixture.json','utf8'));
const browser=await chromium.launch({executablePath:process.env.CHROMIUM_PATH || '/usr/bin/chromium',headless:true,args:['--no-sandbox','--disable-dev-shm-usage','--enable-unsafe-swiftshader']});
try {
 const page=await browser.newPage({viewport:{width:1280,height:900}}),errors=[];
 page.on('pageerror',error=>errors.push(error.message));
 const source=await (await page.request.get(`${origin}/api/projects/${pid}/setups/${sid}`)).json();
 await page.goto(`${origin}/projects/${pid}`);
 await page.locator(`[data-layout-id="${sid}"]`).click();
 await page.getByRole('button',{name:'Edit products together',exact:true}).click();
 await page.getByLabel('Search products or racks',{exact:true}).fill(sku);
 await page.getByLabel(`Name for ${sku}`,{exact:true}).fill('Unsaved draft');
 // Inject one read failure, then retry against the real API and verify the stale draft is discarded.
 await page.route(`**/setups/${sid}/product-edits`,route=>route.fulfill({status:503,contentType:'application/json',body:JSON.stringify({detail:'Offline reload check'})}),{times:1});
 await page.getByRole('button',{name:'Discard edits and reload products',exact:true}).click();
 await page.getByRole('button',{name:'Discard edits and retry products',exact:true}).click();
 await page.getByText(/0 SKUs edited\./).waitFor();
 // Reload also resets search; this SKU can be outside the first 100 catalog rows.
 await page.getByLabel('Search products or racks',{exact:true}).fill(sku);
 await page.waitForFunction(({sku,name})=>Array.from(document.querySelectorAll('input')).some(input=>input.getAttribute('aria-label')===`Name for ${sku}` && input.value===name),{sku,name});
 await page.getByLabel(`Select ${sku}`,{exact:true}).check();
 await page.getByLabel(`Name for ${sku}`,{exact:true}).fill('Offline edited tea');
 await page.getByLabel('Selected product price',{exact:true}).fill('1.005');
 await page.getByRole('button',{name:'Set selected prices',exact:true}).click();
 await page.getByLabel('Selected product promotion',{exact:true}).fill('Scenario input');
 await page.getByRole('button',{name:'Set selected promotions',exact:true}).click();
 await page.getByRole('button',{name:'Preview product changes',exact:true}).click();
 await page.getByRole('button',{name:'Save as new product draft',exact:true}).waitFor();
 await page.screenshot({path:'product-preview.png'});
 // Reach Save at desktop/short/mobile sizes using ordinary wheel scrolling.
 const saveButton=page.getByRole('button',{name:'Save as new product draft',exact:true});
 const reachable=()=>saveButton.evaluate(button=>{
   const rect=button.getBoundingClientRect(),dialog=button.closest('[role="dialog"]').getBoundingClientRect();
   const hit=document.elementFromPoint(rect.x+rect.width/2,rect.y+rect.height/2);
   return rect.top>=Math.max(0,dialog.top) && rect.bottom<=Math.min(innerHeight,dialog.bottom)
     && rect.left>=Math.max(0,dialog.left) && rect.right<=Math.min(innerWidth,dialog.right)
     && !!hit && button.contains(hit);
 });
 for(const viewport of [{width:1280,height:900},{width:1280,height:640},{width:390,height:844}]){
   await page.setViewportSize(viewport);
   // Allow the dialog's 200 ms geometry transition to settle before positioning the pointer.
   await page.waitForTimeout(300);
   const dialog=await page.getByRole('dialog').boundingBox();assert(dialog);
   await page.mouse.move(dialog.x+dialog.width-15,Math.min(viewport.height-30,dialog.y+dialog.height-25));
   for(let i=0;i<15 && !await reachable();i++){await page.mouse.wheel(0,1200);await page.waitForTimeout(150);}
   const rect=await saveButton.boundingBox();
   console.log(JSON.stringify({viewport,rect,dialog:await page.getByRole('dialog').evaluate(e=>({scrollTop:e.scrollTop,scrollHeight:e.scrollHeight,clientHeight:e.clientHeight,rect:e.getBoundingClientRect().toJSON()}))}));
   await page.screenshot({path:`product-${viewport.width}x${viewport.height}.png`,timeout:15000});
   assert(await reachable(),`Save reachable without clipping at ${viewport.width} x ${viewport.height}`);
 }
 const pending=page.waitForResponse(r=>r.url().endsWith('/product-edits/save'));
 await page.getByRole('button',{name:'Save as new product draft',exact:true}).click();
 const savedResponse=await pending;assert(savedResponse.ok(),await savedResponse.text());const saved=await savedResponse.json();
 await page.getByRole('button',{name:'Open edited layout',exact:true}).click();
 await page.locator(`[data-layout-id="${saved.setup_id}"][aria-selected="true"]`).waitFor();
 await page.getByRole('button',{name:'Edit products together',exact:true}).click();
 await page.getByLabel('Search products or racks',{exact:true}).fill(sku);
 assert.equal(await page.getByLabel(`Name for ${sku}`,{exact:true}).inputValue(),'Offline edited tea');
 assert.equal(await page.getByLabel(`Price for ${sku}`,{exact:true}).inputValue(),'1.01');
 const draft=await (await page.request.get(`${origin}/api/projects/${pid}/setups/${saved.setup_id}`)).json();
 const flatten=s=>s.racks.flatMap(r=>r.slots.flatMap(slot=>slot.items));
 const changed=flatten(draft.store).filter(item=>item.sku===sku);
 assert(changed.length>0);assert(changed.every(item=>item.price===101 && item.name==='Offline edited tea' && item.promo==='Scenario input' && item.image_url));
 assert.deepEqual(flatten(draft.store).filter(item=>item.sku!==sku),flatten(source.store).filter(item=>item.sku!==sku));
 const original=await (await page.request.get(`${origin}/api/projects/${pid}/setups/${sid}`)).json();
 assert.deepEqual(original.store,source.store);assert.equal(draft.parentId,sid);assert.deepEqual(errors,[]);
 console.log(JSON.stringify({saved,changedPlacements:changed.length,sourcePreserved:true,cropsPreserved:true,pageErrors:errors}));
} finally {await browser.close();}
