// Run only against the isolated synthetic fixtures described in the queue review.
import assert from 'node:assert/strict';
const {chromium}=await import(process.env.PLAYWRIGHT_MODULE || 'playwright');
const origin=process.env.CAPTURE_TEST_ORIGIN || 'http://127.0.0.1:18766';
const pid='proj_67916afd';
const browser=await chromium.launch({executablePath:process.env.CHROMIUM_PATH||'/usr/bin/chromium',headless:true,args:['--no-sandbox','--disable-dev-shm-usage','--enable-unsafe-swiftshader']});
try {
 const page=await browser.newPage({viewport:{width:1280,height:900}});const errors=[];page.on('pageerror',e=>errors.push(e.message));
 await page.goto(`${origin}/capture/${pid}`);
 if(await page.getByRole('button',{name:'Add photos',exact:true}).count())await page.getByRole('button',{name:'Add photos',exact:true}).click();
 await page.getByLabel('Find products with',{exact:true}).selectOption('classic');await page.getByLabel('Read products with',{exact:true}).selectOption('none');
 await page.getByRole('button',{name:'Choose photos or drop them here'}).click({trial:true});
 await page.getByLabel('Shelf photo files').setInputFiles(['photo-0.png','photo-1.png','duplicate.png']);
 await page.getByText(/0 of 2 ready/).waitFor();assert((await page.getByRole('alert').textContent()).includes('Identical photo'));
 await page.getByRole('button',{name:'Start / resume queue'}).click();await page.getByText(/2 of 2 ready/).waitFor({timeout:60000});
 await page.screenshot({path:'queue-ready.png'});
 // Reach the last review action using ordinary wheel scrolling, without click auto-scroll.
 const panel=page.getByRole('region',{name:'Photo upload queue'});const bounds=await panel.boundingBox();assert(bounds);
 await page.mouse.move(bounds.x+bounds.width/2,Math.min(bounds.y+bounds.height-15,850));
 const reviews=page.getByRole('button',{name:'Review photo'});let rect=await reviews.last().boundingBox();
 for(let i=0;i<10 && !(rect && rect.y>=0 && rect.y+rect.height<=900);i++){await page.mouse.wheel(0,1800);await page.waitForTimeout(150);rect=await reviews.last().boundingBox();}
 console.log(JSON.stringify({panel:bounds,lastReview:rect}));await page.screenshot({path:'queue-wheel.png'});
 assert(rect && rect.y>=0 && rect.y+rect.height<=900,'All review controls must be reachable by ordinary wheel scrolling');
 for(const viewport of [{width:1280,height:640},{width:390,height:844}]){
   await page.setViewportSize(viewport);await page.mouse.move(200,viewport.height-40);
   let last=await reviews.last().boundingBox();
   for(let i=0;i<20 && !(last && last.y>=0 && last.y+last.height<=viewport.height);i++){await page.mouse.wheel(0,1800);await page.waitForTimeout(150);last=await reviews.last().boundingBox();}
   assert(last && last.y>=0 && last.y+last.height<=viewport.height,`Review is reachable at ${viewport.width} x ${viewport.height}`);
   await page.screenshot({path:`queue-${viewport.width}x${viewport.height}.png`});
 }
 await page.setViewportSize({width:1280,height:900});
 const captures=await (await page.request.get(`${origin}/api/projects/${pid}/captures`)).json();
 // Correct each generated scene through the actual editor. These names/prices are explicit test inputs.
 for(const capture of captures.filter(c=>c.image_name.startsWith('photo-'))){
   await page.getByRole('button',{name:'Add photos',exact:true}).click();
   const row=page.getByRole('listitem').filter({has:page.getByText(capture.image_name,{exact:true})});await row.getByRole('button',{name:'Review photo'}).click();
   await page.getByPlaceholder('Product name').first().waitFor();
   while(await page.getByRole('button',{name:'Remove product',exact:true}).count()>1)await page.getByRole('button',{name:'Remove product',exact:true}).last().click();
   await page.getByPlaceholder('Product name').fill(`Offline ${capture.image_name}`);await page.getByPlaceholder('price',{exact:true}).fill('1.99');
   await page.getByRole('button',{name:'Save changes',exact:true}).click();await page.getByRole('button',{name:'Saved',exact:true}).waitFor();
 }
 await page.getByRole('button',{name:'Combine reviewed shelf photos'}).click();await page.getByRole('combobox',{name:/Base layout/}).selectOption('setup_queue_base');await page.getByRole('button',{name:'Select first 20 ready photos'}).click();await page.getByRole('button',{name:'Preview combined layout'}).click();
 await page.getByRole('button',{name:'Save combined draft'}).waitFor();const consent=page.getByRole('checkbox',{name:/Accept .* facings instead/});if(await consent.count())await consent.check();
 const saving=page.waitForResponse(r=>r.url().endsWith('/captures/batch-save'));await page.getByRole('button',{name:'Save combined draft'}).click();const response=await saving;assert(response.ok(),await response.text());const saved=await response.json();
 await page.getByRole('button',{name:'Open combined layout'}).click();await page.waitForURL(`**/projects/${pid}`);
 const draft=await (await page.request.get(`${origin}/api/projects/${pid}/setups/${saved.setup_id}`)).json();const products=draft.store.racks.flatMap(r=>r.slots.flatMap(s=>s.items));assert(products.some(p=>p.name==='Offline photo-0.png'));assert(products.some(p=>p.name==='Offline photo-1.png'));assert(products.every(p=>p.image_url));
 await page.setViewportSize({width:390,height:844});await page.goto(`${origin}/capture/${pid}`);await page.getByRole('button',{name:'Add photos',exact:true}).click();await page.getByRole('region',{name:'Photo upload queue'}).waitFor();await page.screenshot({path:'queue-mobile.png'});
 assert.deepEqual(errors,[]);console.log(JSON.stringify({saved,products:products.map(p=>p.name),pageErrors:errors}));
} finally {await browser.close();}
