import pytest
from app.modules.m20_general_cognitive_worker.software_practice_685_709 import _changelog

def call(changes):return _changelog({'version':'1.0.0','changes':changes})
@pytest.mark.parametrize('entry',[None,5,'x',[],True])
def test_change_entry_must_be_dictionary(entry):
 with pytest.raises(ValueError,match='change entry must be a dict'):call([entry])
@pytest.mark.parametrize('category',[None,5,[],{},'', 'unknown'])
def test_category_must_be_known_string(category):
 with pytest.raises(ValueError,match='category must name a changelog bucket'):call([{'category':category,'description':'x'}])
@pytest.mark.parametrize('category',['added','changed','deprecated','removed','fixed','security'])
def test_category_is_stripped_and_casefolded(category):
 out=call([{'category':' '+category.upper()+' ','description':'x'}])
 assert out['sections'][category]==['x'] and set(out['sections'])=={'added','changed','deprecated','removed','fixed','security'}
@pytest.mark.parametrize('description',[None,5,[],{},'', '   '])
def test_description_must_be_nonblank_string(description):
 with pytest.raises(ValueError,match='description must be a nonempty string'):call([{'category':'added','description':description}])
def test_empty_changes_refused():
 with pytest.raises(ValueError,match='nonempty changes list required'):call([])
