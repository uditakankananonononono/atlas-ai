import json
from pathlib import Path

ROOT=Path(__file__).parents[1]
FRONTEND=ROOT/'frontend'


def package(): return json.loads((FRONTEND/'package.json').read_text())

def lock(): return json.loads((FRONTEND/'package-lock.json').read_text())


def test_a01_next14_is_installed_and_app_router_build_source_exists():
    assert package()['dependencies']['next']=='14.2.32'
    assert lock()['packages']['node_modules/next']['version']=='14.2.32'
    assert (FRONTEND/'app/layout.tsx').is_file() and (FRONTEND/'app/page.tsx').is_file()
    assert not (FRONTEND/'pages/_app.tsx').exists()


def test_a02_react18_runtime_and_types_are_installed_consistently():
    p=package(); installed=lock()['packages']
    assert p['dependencies']['react']=='18.3.1' and p['dependencies']['react-dom']=='18.3.1'
    assert installed['node_modules/react']['version']=='18.3.1'
    assert installed['node_modules/react-dom']['version']=='18.3.1'
    assert installed['node_modules/@types/react']['version'].startswith('18.')
    assert installed['node_modules/@types/react-dom']['version'].startswith('18.')


def test_a03_tailwind_is_compiled_from_real_app_and_component_sources():
    p=package(); config=(FRONTEND/'tailwind.config.ts').read_text(); css=(FRONTEND/'app/globals.css').read_text()
    assert p['devDependencies']['tailwindcss'].startswith('^3.4')
    assert 'app/**/*' in config and 'components/**/*' in config
    assert '@tailwind base' in css and '@tailwind components' in css and '@tailwind utilities' in css
    assert 'className=' in (FRONTEND/'app/page.tsx').read_text()


def test_a04_shadcn_style_owned_component_uses_radix_and_local_source():
    p=package(); card=(FRONTEND/'components/ui/card.tsx').read_text()
    assert '@radix-ui/react-dialog' in p['dependencies'] and '@radix-ui/react-tabs' in p['dependencies']
    assert 'React.forwardRef' in card and 'cn(' in card
    assert not (FRONTEND/'node_modules/shadcn').exists()


def test_a05_react_flow_is_rendered_by_real_knowledge_workspace():
    p=package(); source=(FRONTEND/'components/KnowledgeWorkspace.tsx').read_text()
    assert p['dependencies']['@xyflow/react'].startswith('^12.')
    for symbol in ('ReactFlow','Background','MiniMap','Controls'):
        assert symbol in source
    assert 'nodeTypes={nodeTypes}' in source and 'fitView' in source


def test_a06_recharts_responsive_accessible_chart_is_real_component():
    p=package(); source=(FRONTEND/'components/OperationsChart.tsx').read_text()
    assert p['dependencies']['recharts'].startswith('^2.')
    assert 'ResponsiveContainer' in source and 'LineChart' in source and 'Line' in source
    assert 'aria-label="Operations metric chart"' in source
