import pytest
from app.mission_build.enclosure import generate


def test_mesh_has_open_top_cavity_closed_material_boundary_and_analytic_volume():
    r = generate(dict(width_mm=80,depth_mm=50,height_mm=25,wall_mm=2))
    assert r['manifold_closed_surface'] and len(r['triangles']) == 28
    assert r['material_volume_mm3'] == pytest.approx(80*50*25-76*46*23)
    assert r['interior_mm'] == [76,46,23] and not r['manufactured']
    assert 'difference()' in r['openscad'] and len(r['obj'].splitlines()) == 45


@pytest.mark.parametrize('key,value', [('width_mm',True),('height_mm',float('nan')),('wall_mm',25),('depth_mm',-1),('width_mm',1001)])
def test_invalid_geometry(key,value):
    p = dict(width_mm=80,depth_mm=50,height_mm=25,wall_mm=2);p[key]=value
    with pytest.raises(ValueError):generate(p)
