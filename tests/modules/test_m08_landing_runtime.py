import json
import pytest
from pydantic import ValidationError
from app.modules.m08_startup_growth.schemas import LandingPageIn
from app.modules.m08_startup_growth.landing_runtime import landing_files


@pytest.mark.parametrize('text', ['{process.exit()}', '</h1><script>alert(1)</script>', 'Quote " slash \\ & amp <tag>', 'অসমীয়া 🚀', '\u2028\u2029'])
def test_user_text_only_in_json(text):
    files = landing_files(LandingPageIn(project_id='p', product_name=text, hero=text + ' hero', features=[text]))
    data = json.loads(files['app/content.json'])
    assert data == {'product_name': text, 'hero': text + ' hero', 'features': [text]}
    assert 'content.product_name' in files['app/page.tsx']
    assert 'content.features.map' in files['app/page.tsx']
    assert text not in files['app/page.tsx']


def test_complete_config_and_server_secret_boundary():
    files = landing_files(LandingPageIn(project_id='p', product_name='Atlas', hero='Ship safely', features=['Approvals']))
    required = {'package.json', 'tsconfig.json', 'app/layout.tsx', 'app/page.tsx', 'postcss.config.mjs', 'tailwind.config.ts', 'next.config.mjs', 'app/api/waitlist/route.ts', 'supabase/waitlist.sql'}
    assert required <= files.keys()
    assert json.loads(files['package.json'])['scripts']['build'] == 'next build --webpack'
    assert all('SUPABASE_SERVICE_ROLE_KEY' not in text for name, text in files.items() if name in {'app/page.tsx', 'app/layout.tsx', 'app/content.json'})
    assert 'ENABLE ROW LEVEL SECURITY' in files['supabase/waitlist.sql']


@pytest.mark.parametrize('table', ['bad-name', 'waitlist";DROP TABLE users;', 'x.y', '9bad'])
def test_sql_identifier_guard(table):
    with pytest.raises(ValidationError):
        LandingPageIn(project_id='p', product_name='Atlas', hero='Ship safely', features=['A'], waitlist_table=table)
