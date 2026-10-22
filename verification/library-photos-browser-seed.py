"""Use backend Python from a fresh, disposable working directory."""
from pathlib import Path
import io
from PIL import Image
from store_emulator.application.storage.seed import seed_sample_projects
from store_emulator.application.storage.io import write_json
from store_emulator.application.storage.setups import new_setup_data, setup_path
from store_emulator.application.setups import set_active_setup
from store_emulator.domain.rack import Rack, Slot, SlotItem
from store_emulator.domain.store import Store
if Path('.data').exists():
    raise SystemExit('Use a fresh directory; existing data is preserved.')
seed_sample_projects()
pid, sid = 'proj_67916afd', 'setup_photos_fixture'
store = Store(id='photos_fixture', name='Product photos fixture', type='convenience', currency='USD', grid_size=(12, 12), racks=[
    Rack(id='in', type='entrance', shape=[[1]], position=(0, 11)),
    Rack(id='out', type='exit', shape=[[1]], position=(11, 11)),
    Rack(id='shelf', rack_name='Tea shelf', type='shelf', shape=[[1]], position=(2, 2), slots=[
        Slot(block=0, face='S', level=1, items=[SlotItem(sku='tea', name='Tea', price=231, regular_price=299, promo='Local'), SlotItem(sku='sample', name='Sample', price=0)]),
        Slot(block=0, face='W', level=4, items=[SlotItem(sku='tea', name='Tea', price=231)])]),
])
source = new_setup_data('Product photos fixture', None, store.model_dump(mode='json')); source['id'] = sid
write_json(setup_path(pid, sid), source); set_active_setup(pid, sid)
photo = io.BytesIO(); Image.new('RGB', (32, 40), 'blue').save(photo, format='PNG'); Path('synthetic-tea.png').write_bytes(photo.getvalue())
print('Seeded synthetic products and a test packshot, no real store data or model calls.')
