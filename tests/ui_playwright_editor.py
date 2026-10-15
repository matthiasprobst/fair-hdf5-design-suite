"""Canvas regression tests against a running frontend and real Python API.

Run after starting app.py and Vite:
  FAIR_UI_URL=http://127.0.0.1:5173 .venv/bin/python tests/ui_playwright_editor.py
Optional: FAIR_BROWSER_EXECUTABLE=/path/to/chromium, FAIR_SCREENSHOT_DIR=/tmp/fair-editor-qa
Screenshots deliberately live outside the source tree. No store/test hooks are used.
"""
from __future__ import annotations

import copy
import json
import os
import re
from pathlib import Path
import sys
import unittest

from playwright.sync_api import sync_playwright, expect

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backend import CATALOG, demo

URL = os.environ.get('FAIR_UI_URL', 'http://127.0.0.1:5173')
OUT = Path(os.environ.get('FAIR_SCREENSHOT_DIR', '/tmp/fair-editor-qa'))
KEY = 'fair-hdf5-react-v2-blueprint'
BASE = {'name': 'Canvas regression', 'version': '0.1', 'nodes': [
    {'id': id, 'type': kind, 'label': label, 'x': x, 'y': 100.25,
     'config': copy.deepcopy(CATALOG[kind]['defaults'])}
    for id, kind, label, x in [('fan', 'fan', 'Test fan', 40.5),
                               ('sensor', 'pressure_sensor', 'Test sensor', 390.5),
                               ('daq', 'daq', 'Test logger', 740.5)]
], 'edges': []}


class EditorBrowserTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.playwright = sync_playwright().start()
        kwargs = {'headless': True, 'args': ['--no-sandbox']}
        if os.environ.get('FAIR_BROWSER_EXECUTABLE'):
            kwargs['executable_path'] = os.environ['FAIR_BROWSER_EXECUTABLE']
        try:
            cls.browser = cls.playwright.chromium.launch(**kwargs)
        except Exception:
            cls.playwright.stop()
            raise
        OUT.mkdir(parents=True, exist_ok=True)

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls.playwright.stop()

    def setUp(self):
        self.context = self.browser.new_context(viewport={'width': 1672, 'height': 941})
        # Exclude external font/network noise from app console assertions.
        self.context.route('https://fonts.googleapis.com/**', lambda r: r.fulfill(body=''))
        self.context.route('https://fonts.gstatic.com/**', lambda r: r.fulfill(body=''))
        self.page = self.context.new_page()
        self.errors = []
        self.expected_http_statuses = set()
        self.page.on('pageerror', lambda error: self.errors.append(str(error)))
        self.page.on('console', self.check_console)
        self.preview_requests = []
        self.page.on('request', lambda r: self.preview_requests.append(r.post_data) if r.url.endswith('/api/preview') else None)

    def check_console(self, message):
        # Existing hideAttribution configuration also warns in the unchanged baseline.
        # Keep this exact library notice separate from runtime/layout warnings.
        if message.type == 'warning' and message.text.startswith(
                'React Flow: It seems like you are hiding the attribution.'):
            return
        if message.type in ('error', 'warning') and not any(
                f'status of {code}' in message.text for code in self.expected_http_statuses):
            self.errors.append(message.text)

    def tearDown(self):
        try:
            self.assertEqual(self.errors, [], 'Browser console must remain clean')
        finally:
            self.context.close()

    def load(self, blueprint=BASE, raw=None):
        raw = json.dumps(blueprint) if raw is None else raw
        self.page.add_init_script(f"""if (!sessionStorage.getItem('test-seeded')) {{
            localStorage.setItem({json.dumps(KEY)}, {json.dumps(raw)});
            sessionStorage.setItem('test-seeded','yes');
        }}""")
        self.page.goto(URL)
        expect(self.page).to_have_title('FAIR Data Design Suite')
        self.assertTrue(self.page.url.startswith(URL))
        expect(self.page.get_by_role('heading', name='Target HDF5 Design')).to_be_visible()
        self.assertEqual(self.page.locator('vite-error-overlay').count(), 0)

    def graph_visible(self, count):
        expect(self.page.locator('.react-flow__node')).to_have_count(count)
        self.page.wait_for_function('''count => {
            const nodes = [...document.querySelectorAll('.react-flow__node')];
            return nodes.length === count && nodes.every(n => {
                const b=n.getBoundingClientRect(), s=getComputedStyle(n);
                return b.width > 0 && b.height > 0 && s.visibility === 'visible' && s.display !== 'none';
            });
        }''', arg=count)
        self.assertEqual(self.page.locator('vite-error-overlay').count(), 0)
        self.settled_viewport()

    def node(self, id):
        return self.page.locator(f'.react-flow__node[data-id="{id}"]')

    def stored(self):
        return self.page.evaluate('(key)=>JSON.parse(localStorage.getItem(key))', KEY)

    def wait_saved(self):
        expect(self.page.locator('.saved-text')).to_contain_text('Saved locally')

    def settled_viewport(self):
        self.page.evaluate("""() => new Promise(resolve => {
            let previous='', stable=0;
            function frame() {
                const value=document.querySelector('.react-flow__viewport').style.transform;
                stable=value===previous ? stable+1 : 0;
                previous=value;
                if(stable>=3)resolve(); else requestAnimationFrame(frame);
            }
            requestAnimationFrame(frame);
        })""")

    def viewport(self):
        return self.page.locator('.react-flow__viewport').evaluate('(e)=>e.style.transform')

    def position(self, id):
        return self.node(id).evaluate('(e)=>({x:new DOMMatrix(e.style.transform).m41,y:new DOMMatrix(e.style.transform).m42})')

    def drag_node(self, id, dx, dy):
        old = self.position(id)
        box = self.node(id).locator('.node-title').bounding_box()
        zoom = self.page.locator('.react-flow__viewport').evaluate('(e)=>new DOMMatrix(e.style.transform).a')
        viewport = self.viewport()
        self.page.mouse.move(box['x']+box['width']/2, box['y']+box['height']/2)
        self.page.mouse.down()
        # Cross React Flow's activation threshold before measuring the actual drag.
        # At low zoom, counting that dead zone as node movement makes this helper fail
        # even on the unchanged frontend (e.g. the 250-node graph).
        self.page.mouse.move(box['x']+box['width']/2+4, box['y']+box['height']/2)
        self.page.mouse.move(box['x']+box['width']/2+4+dx, box['y']+box['height']/2+dy, steps=12)
        self.page.mouse.up()
        self.page.wait_for_function('''([id,x])=>new DOMMatrix(document.querySelector(`.react-flow__node[data-id="${id}"]`).style.transform).m41!==x''', arg=[id, old['x']])
        self.wait_saved()
        new = self.position(id)
        self.assertAlmostEqual(new['x']-old['x'], dx/zoom, delta=2)
        self.assertAlmostEqual(new['y']-old['y'], dy/zoom, delta=2)
        saved = next(n for n in self.stored()['nodes'] if n['id']==id)
        self.assertAlmostEqual(saved['x'], new['x'], delta=.01)
        self.assertAlmostEqual(saved['y'], new['y'], delta=.01)
        self.assertEqual(self.viewport(), viewport, 'Ordinary dragging must not fit the viewport')
        self.graph_visible(len(self.stored()['nodes']))

    def connect(self, source, target):
        a = self.node(source).locator('[data-handleid="out"]').bounding_box()
        b = self.node(target).locator('[data-handleid="in"]').bounding_box()
        self.page.mouse.move(a['x']+a['width']/2, a['y']+a['height']/2)
        self.page.mouse.down()
        self.page.mouse.move(b['x']+b['width']/2, b['y']+b['height']/2, steps=15)
        self.page.mouse.up()

    def import_graph(self, blueprint):
        self.page.locator('input[type=file][accept*=".json"]').set_input_files({
            'name':'blueprint.json', 'mimeType':'application/json', 'buffer':json.dumps(blueprint).encode()})
        expect(self.page.get_by_label('Experiment title')).to_have_value(blueprint['name'])
        self.graph_visible(len(blueprint['nodes']))
        self.wait_saved()

    def test_drag_drop_move_connect_cancel_edit_delete_reload(self):
        self.load()
        self.graph_visible(3)
        expect(self.page.locator('.artifact-shacl .artifact-status')).to_contain_text('Ready')
        # Zoom and pan with real pointer input before dropping a palette item.
        before = self.viewport()
        self.page.get_by_title('Zoom out', exact=True).click()
        self.page.wait_for_function('(before)=>document.querySelector(".react-flow__viewport").style.transform!==before', arg=before)
        self.settled_viewport()
        # Pan from empty canvas using the pointer.
        self.page.locator('.react-flow__pane').click(position={'x':30,'y':30})
        self.page.mouse.move(300,220)
        self.page.mouse.down()
        self.page.mouse.move(335,245,steps=8)
        self.page.mouse.up()
        palette=self.page.locator('.palette-item').filter(has_text='Temperature sensor')
        canvas=self.page.locator('.canvas-region')
        box=canvas.bounding_box()
        transform=self.page.locator('.react-flow__viewport').evaluate('(e)=>{const m=new DOMMatrix(e.style.transform);return {x:m.m41,y:m.m42,z:m.a}}')
        palette.drag_to(canvas,target_position={'x':box['width']*.5,'y':box['height']*.78})
        self.graph_visible(4)
        self.wait_saved()
        added=next(n for n in self.stored()['nodes'] if n['id'] not in ('fan','sensor','daq'))
        self.assertEqual(added['type'],'temperature_sensor')
        self.assertAlmostEqual(added['x'],(box['width']*.5-transform['x'])/transform['z']-95,delta=2)
        self.assertAlmostEqual(added['y'],(box['height']*.78-transform['y'])/transform['z']-38,delta=2)
        self.page.screenshot(path=str(OUT/'before-movement.png'),full_page=True)
        expect(self.page.locator('.artifact-shacl .artifact-status')).to_contain_text('Ready')
        before_requests=len(self.preview_requests)
        for dx,dy in [(28,15),(-19,-9),(12,8)]:
            self.drag_node(added['id'],dx,dy)
        self.assertEqual(len(self.preview_requests),before_requests,'Movement must not schedule previews')
        self.page.screenshot(path=str(OUT/'after-movement.png'),full_page=True)
        viewport=self.viewport()
        self.connect('fan','sensor')
        expect(self.page.locator('.react-flow__edge')).to_have_count(1)
        self.wait_saved()
        self.assertEqual([(e['source'],e['target']) for e in self.stored()['edges']],[('fan','sensor')])
        self.assertEqual(self.viewport(),viewport)
        self.graph_visible(4)
        self.page.screenshot(path=str(OUT/'after-connection.png'),full_page=True)
        # Duplicate and self connections are rejected; cancelling on empty canvas is inert.
        self.connect('fan','sensor')
        self.connect('fan','fan')
        source=self.node('sensor').locator('[data-handleid="out"]').bounding_box()
        self.page.mouse.move(source['x']+source['width']/2,source['y']+source['height']/2)
        self.page.mouse.down()
        self.page.mouse.move(box['x']+40,box['y']+40,steps=10)
        self.page.keyboard.press('Escape')
        self.page.mouse.up()
        expect(self.page.locator('.react-flow__edge')).to_have_count(1)
        self.graph_visible(4)
        self.node(added['id']).locator('.node-title').click()
        self.page.locator('.form-field').filter(has=self.page.locator('label',has_text='Block name')).locator('input').fill('Edited temperature sensor')
        self.page.get_by_label('New metadata field').fill('calibration_note')
        self.page.get_by_role('button',name='Add field',exact=True).click()
        self.page.locator('.metadata-row').filter(has_text='calibration note').locator('input').fill('Checked in regression')
        self.wait_saved()
        self.assertEqual(next(n for n in self.stored()['nodes'] if n['id']==added['id'])['config']['calibration_note'],'Checked in regression')
        self.assertEqual(self.viewport(),viewport)
        self.graph_visible(4)
        # Keyboard edge deletion then node deletion also clears the inspector.
        self.page.locator('.react-flow__edge').focus()
        self.page.keyboard.press('Enter')
        self.page.keyboard.press('Delete')
        expect(self.page.locator('.react-flow__edge')).to_have_count(0)
        self.connect('fan','sensor')
        expect(self.page.locator('.react-flow__edge')).to_have_count(1)
        self.node('sensor').locator('.node-title').click()
        self.page.keyboard.press('Delete')
        self.graph_visible(3)
        expect(self.page.locator('.react-flow__edge')).to_have_count(0)
        expect(self.page.get_by_text('Select a building block',exact=True)).to_be_visible()
        self.wait_saved()
        saved=self.stored()
        self.page.reload()
        self.graph_visible(3)
        self.assertEqual(self.stored(),saved)
        self.assertEqual(self.node(added['id']).locator('.node-title').inner_text(),'Edited temperature sensor')
        for n in saved['nodes']:
            pos=self.position(n['id'])
            self.assertAlmostEqual(pos['x'],n['x'],delta=.01)
            self.assertAlmostEqual(pos['y'],n['y'],delta=.01)
        self.page.screenshot(path=str(OUT/'after-reload.png'),full_page=True)

    def test_validation_survives_layout_but_not_metadata(self):
        self.load()
        self.graph_visible(3)
        self.page.get_by_role('button',name='Validate',exact=True).click()
        expect(self.page.get_by_text('All modeled checks passed',exact=True)).to_be_visible()
        self.page.get_by_role('button',name='Close',exact=True).last.click()
        self.drag_node('sensor',20,10)
        expect(self.page.locator('.artifact-validation .artifact-status')).to_contain_text('Passed')
        self.node('sensor').locator('.node-title').click()
        self.page.locator('.form-field').filter(has=self.page.locator('label',has_text='Block name')).locator('input').fill('Changed semantics')
        expect(self.page.locator('.artifact-validation .artifact-status')).to_contain_text('Stale')
        expect(self.page.get_by_role('button',name='View report')).to_be_disabled()

    def test_import_reset_malformed_input_and_large_graph(self):
        self.load()
        self.graph_visible(3)
        raw_before=self.stored()
        self.page.locator('input[type=file][accept*=".json"]').set_input_files({'name':'bad.json','mimeType':'application/json','buffer':b'{"nodes":false}'})
        expect(self.page.get_by_role('status')).to_contain_text('Invalid blueprint')
        self.assertEqual(self.stored(),raw_before)
        large={'name':'250 blocks','version':'0.1','nodes':[], 'edges':[]}
        for i in range(250):
            n=copy.deepcopy(BASE['nodes'][0]);n.update(id=f'node_{i}',x=(i%20)*240.125,y=(i//20)*190.25);n['config']['path']=f'/experiment/fan_{i}';large['nodes'].append(n)
        self.import_graph(large)
        self.drag_node('node_126',4,2)
        self.page.screenshot(path=str(OUT/'250-nodes.png'),full_page=True)
        replacement=copy.deepcopy(BASE);replacement['name']='Imported layout'
        self.import_graph(replacement)
        self.drag_node('fan',25,8)
        self.page.get_by_role('button',name='Project',exact=True).click()
        self.page.once('dialog',lambda dialog:dialog.accept())
        self.page.get_by_role('button',name='Reset example',exact=True).click()
        self.graph_visible(len(demo()['nodes']))
        self.wait_saved()
        self.page.reload()
        self.graph_visible(len(demo()['nodes']))

    def test_slow_initialization_and_saved_invalid_semantics(self):
        # Hold catalog delivery until the loading screen is observed.
        held=[]
        self.page.route('**/api/catalog',lambda route:held.append(route))
        invalid=copy.deepcopy(BASE);invalid['nodes'][0]['config']['path']=''
        # This draft is structurally editable but fails the real backend's path check.
        self.expected_http_statuses.add(422)
        self.page.add_init_script(f"if(!sessionStorage.getItem('invalid-seeded')){{localStorage.setItem({json.dumps(KEY)},{json.dumps(json.dumps(invalid))});sessionStorage.setItem('invalid-seeded','yes')}}")
        self.page.goto(URL,wait_until='domcontentloaded')
        expect(self.page.get_by_text('Loading research data workspace')).to_be_visible()
        self.page.wait_for_function('document.querySelector(".app-loading")!==null')
        self.page.unroute('**/api/catalog')
        # StrictMode can initiate and abort an earlier catalog request.
        for route in held:
            try:
                route.fulfill(status=200,content_type='application/json',body=json.dumps({'catalog':CATALOG,'profile_source':'test'}))
            except Exception:
                pass
        self.graph_visible(3)
        self.assertEqual(self.stored()['nodes'][0]['config']['path'],'')
        self.assertEqual(self.stored()['name'],invalid['name'])
        expect(self.page.get_by_role('alert')).to_contain_text('invalid absolute HDF5 path')
        self.page.reload()
        self.graph_visible(3)
        self.assertEqual(self.stored()['nodes'][0]['config']['path'],'')
        self.node('fan').locator('.node-title').click()
        self.page.locator('.form-field').filter(has=self.page.locator('label',has_text='Target path (HDF5)')).locator('input').fill('/repaired')
        expect(self.page.locator('.artifact-shacl .artifact-status')).to_contain_text('Ready')
        self.wait_saved()
        self.assertEqual(self.stored()['nodes'][0]['config']['path'],'/repaired')

    def test_unavailable_storage_still_allows_edit_and_export(self):
        self.page.add_init_script("Storage.prototype.getItem = function(){throw new Error('storage denied')}; Storage.prototype.setItem = function(){throw new Error('storage denied')}")
        self.page.goto(URL)
        expect(self.page.get_by_role('alert')).to_contain_text('storage denied')
        expect(self.page.get_by_role('heading',name='Target HDF5 Design')).to_be_visible()
        self.page.get_by_label('Experiment title').fill('Recoverable editor')
        self.page.get_by_role('button',name='Project',exact=True).click()
        with self.page.expect_download() as transfer:
            self.page.get_by_role('button',name='Export blueprint JSON').click()
        exported=json.loads(Path(transfer.value.path()).read_text())
        self.assertEqual(exported['name'],'Recoverable editor')

    def test_malformed_saved_draft_is_recoverable(self):
        self.load(raw='{damaged')
        self.graph_visible(0)
        self.assertEqual(self.page.evaluate('(key)=>localStorage.getItem(key)',KEY),'{damaged')
        with self.page.expect_download() as transfer:
            self.page.get_by_role('button',name='Export original draft').click()
        self.assertEqual(Path(transfer.value.path()).read_text(),'{damaged')
        self.import_graph(BASE)
        self.assertEqual(self.page.evaluate('(key)=>localStorage.getItem(key)',KEY+'-recovery'),'{damaged')
        # Exports must not contain any React Flow or rendering state.
        self.page.get_by_role('button',name='Project',exact=True).click()
        with self.page.expect_download() as transfer:
            self.page.get_by_role('button',name='Export blueprint JSON').click()
        exported=json.loads(Path(transfer.value.path()).read_text())
        self.assertEqual(set(exported),{'name','version','nodes','edges'})
        for node in exported['nodes']:
            self.assertEqual(set(node),{'id','type','label','x','y','config'})


    def assert_layout_bounds(self):
        dimensions = self.page.evaluate('''() => {
            const root=document.documentElement;
            const selectors=['.global-header','.project-toolbar','.main-stage',
                '.canvas-region','.artifacts-container','.statusbar'];
            return {documentWidth:root.scrollWidth, width:innerWidth,
                boxes:selectors.map(selector=>{
                    const r=document.querySelector(selector).getBoundingClientRect();
                    return {selector,left:r.left,right:r.right,width:r.width,height:r.height};
                })};
        }''')
        self.assertLessEqual(dimensions['documentWidth'], dimensions['width'])
        for box in dimensions['boxes']:
            self.assertGreater(box['width'], 0, box['selector'])
            self.assertGreater(box['height'], 0, box['selector'])
            self.assertGreaterEqual(box['left'], 0, box['selector'])
            self.assertLessEqual(box['right'], dimensions['width'], box['selector'])
        expect(self.page.locator('vite-error-overlay')).to_have_count(0)
        self.assertTrue(self.page.locator('.toolbar-buttons').evaluate('''element => {
            const boxes=[...element.querySelectorAll(':scope > button, :scope > .project-menu-wrap')]
                .map(e=>e.getBoundingClientRect());
            return boxes.every((a,i)=>boxes.every((b,j)=>i===j ||
                a.right<=b.left || b.right<=a.left || a.bottom<=b.top || b.bottom<=a.top));
        }'''), 'Project actions must not overlap')

    def test_layout_resize_preserves_canvas_and_desktop_preference(self):
        self.load()
        self.graph_visible(3)
        expect(self.page.locator('.artifact-shacl .artifact-status')).to_contain_text('Ready')
        self.node('fan').locator('.node-title').click()
        self.page.get_by_title('Zoom out', exact=True).click()
        self.settled_viewport()
        # Explicit pan verifies both transform components survive layout changes.
        canvas = self.page.locator('.canvas-region').bounding_box()
        self.page.mouse.move(canvas['x']+40, canvas['y']+40)
        self.page.mouse.down()
        self.page.mouse.move(canvas['x']+60, canvas['y']+55, steps=5)
        self.page.mouse.up()
        self.settled_viewport()
        transform = self.viewport()
        saved = self.stored()
        requests = len(self.preview_requests)
        canvas_element = self.page.locator('.react-flow').element_handle()
        width = self.page.locator('.canvas-region').bounding_box()['width']
        self.page.get_by_role('button', name='Close inspector', exact=True).click()
        expect(self.page.locator('#workbench-inspector')).to_be_hidden()
        self.assertGreater(self.page.locator('.canvas-region').bounding_box()['width'], width+250)
        expect(self.page.get_by_role('button', name='Toggle inspector', exact=True)).to_be_focused()
        for w,h in [(1440,900),(1150,768),(1149,768),(1024,768),(768,600),(1149,768),(1150,768),(1672,941)]:
            with self.subTest(viewport=(w,h)):
                self.page.set_viewport_size({'width':w,'height':h})
                expect(self.page.locator('.main-stage')).to_have_attribute('data-compact', str(w<1150).lower())
                self.assert_layout_bounds()
                self.assertEqual(self.viewport(), transform)
                self.assertTrue(canvas_element.evaluate('e=>e.isConnected && e===document.querySelector(".react-flow")'))
                expect(self.node('fan')).to_have_class(re.compile(r'.*selected.*'))
                expect(self.page.locator('#workbench-inspector')).to_be_hidden()
                self.assertEqual(self.stored(), saved)
                self.page.screenshot(path=str(OUT/f'layout-{w}.png'))
        self.assertEqual(len(self.preview_requests), requests)
        self.page.get_by_role('button', name='Toggle inspector', exact=True).click()
        expect(self.page.locator('#workbench-inspector')).to_be_visible()
        self.assertAlmostEqual(self.page.locator('.canvas-region').bounding_box()['width'], width, delta=1)
        self.assertEqual(self.viewport(), transform)

    def test_compact_panels_keyboard_add_drag_and_edit(self):
        self.page.set_viewport_size({'width':768,'height':600})
        self.load()
        self.graph_visible(3)
        library = self.page.get_by_role('button', name='Toggle block library', exact=True)
        inspector = self.page.get_by_role('button', name='Toggle inspector', exact=True)
        expect(self.page.locator('#workbench-library')).to_be_hidden()
        expect(self.page.locator('#workbench-inspector')).to_be_hidden()
        # The empty inspector can also be closed, without selecting a node first.
        inspector.click()
        self.page.get_by_role('button', name='Close inspector', exact=True).click()
        expect(inspector).to_be_focused()
        library.focus()
        self.page.keyboard.press('Enter')
        expect(library).to_have_attribute('aria-expanded','true')
        self.page.get_by_label('Search components').fill('Temperature')
        self.page.keyboard.press('Escape')
        expect(library).to_be_focused()
        expect(self.page.locator('#workbench-library')).to_be_hidden()
        library.click()
        expect(self.page.get_by_label('Search components')).to_have_value('Temperature')
        item = self.page.locator('.palette-item').filter(has_text='Temperature sensor')
        item.hover()
        self.page.get_by_role('button',name='Add Temperature sensor',exact=True).click()
        self.graph_visible(4)
        expect(self.page.locator('#workbench-library')).to_be_hidden()
        expect(self.page.locator('#workbench-inspector')).to_be_visible()
        self.page.locator('.form-field').filter(has=self.page.locator('label',has_text='Block name')).locator('input').fill('Compact sensor')
        self.wait_saved()
        self.assertEqual(self.stored()['nodes'][-1]['label'], 'Compact sensor')
        self.page.keyboard.press('Escape')
        expect(inspector).to_be_focused()
        library.click()
        self.page.get_by_label('Search components').fill('Pressure')
        # The nonmodal panel permits a real drop onto the exposed part of the canvas.
        canvas=self.page.locator('.canvas-region')
        box=canvas.bounding_box()
        self.page.locator('.palette-item').filter(has_text='Pressure sensor').drag_to(
            canvas, target_position={'x':box['width']*.55,'y':box['height']*.5})
        self.graph_visible(5)
        self.wait_saved()
        expect(self.page.locator('#workbench-inspector')).to_be_visible()
        self.assertEqual(self.stored()['nodes'][-1]['type'], 'pressure_sensor')
        self.page.get_by_role('button', name='Close inspector', exact=True).click()
        # Nodes added after the resize remain movable; use the latest selected node.
        self.drag_node(self.stored()['nodes'][-1]['id'], 12, -8)
        self.page.screenshot(path=str(OUT/'compact-editor.png'))
        # Crossing back restores the original open desktop inspector preference.
        self.page.set_viewport_size({'width':1440,'height':900})
        expect(self.page.locator('#workbench-inspector')).to_be_visible()
        self.page.set_viewport_size({'width':768,'height':600})
        expect(self.page.locator('#workbench-inspector')).to_be_hidden()

    def test_compact_actions_and_internal_scrolling(self):
        self.page.set_viewport_size({'width':768,'height':600})
        blueprint=copy.deepcopy(BASE)
        blueprint['name']='A long project title ' * 30
        blueprint['nodes'][0]['label']='VeryLongUnbrokenLabel' * 30
        blueprint['nodes'][0]['config'].update({f'custom_{i}':'Extensive metadata' * 20 for i in range(50)})
        self.load(blueprint)
        self.graph_visible(3)
        self.assert_layout_bounds()
        self.page.get_by_role('button',name='Application menu',exact=True).click()
        self.page.get_by_role('navigation').get_by_role('button',name='Projects',exact=True).click()
        expect(self.page.get_by_role('dialog')).to_be_visible()
        self.page.get_by_role('dialog').get_by_role('button',name='Close',exact=True).last.click()
        self.page.get_by_role('button',name='Project',exact=True).click()
        expect(self.page.get_by_role('button',name='Import blueprint JSON',exact=True)).to_be_visible()
        expect(self.page.get_by_role('button',name='Validate existing .h5',exact=True)).to_be_visible()
        with self.page.expect_download() as transfer:
            self.page.get_by_role('button',name='Export blueprint JSON',exact=True).click()
        self.assertEqual(json.loads(Path(transfer.value.path()).read_text()), blueprint)
        self.node('fan').locator('.node-title').click()
        expect(self.page.locator('#workbench-inspector')).to_be_visible()
        self.assert_layout_bounds()
        self.assertTrue(self.page.locator('.inspector-scroll').evaluate('(e)=>e.scrollHeight>e.clientHeight'))
        self.page.get_by_role('button',name='Duplicate',exact=True).scroll_into_view_if_needed()
        self.assertGreater(self.page.locator('.inspector-scroll').evaluate('(e)=>e.scrollTop'), 0)
        self.page.get_by_role('button',name='Close inspector',exact=True).click()
        self.page.get_by_role('button',name='Toggle block library',exact=True).click()
        self.assertTrue(self.page.locator('.palette-scroll').evaluate('(e)=>e.scrollHeight>e.clientHeight'))
        self.page.locator('.palette-foot').scroll_into_view_if_needed()
        self.page.get_by_role('button',name='Close block library',exact=True).click()
        report=self.page.get_by_role('button',name='Run validation',exact=True)
        report.scroll_into_view_if_needed()
        self.assertGreater(self.page.locator('.artifacts-grid').evaluate('(e)=>e.scrollTop'), 0)
        self.assert_layout_bounds()
        self.page.screenshot(path=str(OUT/'compact-artifacts.png'))
        # Short windows use the shell's content scroll instead of clipping actions.
        self.page.set_viewport_size({'width':768,'height':420})
        self.page.locator('.statusbar').scroll_into_view_if_needed()
        self.assertGreater(self.page.locator('.app-content').evaluate('(e)=>e.scrollTop'), 0)
        self.assert_layout_bounds()

    def test_layout_with_long_storage_error(self):
        self.page.set_viewport_size({'width':768,'height':600})
        self.page.add_init_script("Storage.prototype.getItem=function(){throw new Error('storage-denied-'.repeat(100))}")
        self.page.goto(URL)
        expect(self.page.get_by_role('alert')).to_contain_text('storage-denied')
        expect(self.page.get_by_role('heading',name='Target HDF5 Design')).to_be_visible()
        self.assert_layout_bounds()
        self.assertLessEqual(self.page.get_by_role('alert').bounding_box()['height'],96)
        self.page.locator('.statusbar').scroll_into_view_if_needed()
        self.page.screenshot(path=str(OUT/'compact-storage-error.png'))


if __name__=='__main__':
    unittest.main(verbosity=2)
