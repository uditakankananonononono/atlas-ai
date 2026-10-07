import pytest
from app.modules.m20_general_cognitive_worker.tools import ToolRegistry, ToolBlockedError, ToolError
from app.modules.m20_general_cognitive_worker.schemas import ToolSpec

async def handler(args):return args


def test_schema_export_matches_registered_schema_and_is_detached():
    parameters={'type':'object','properties':{'nested':{'type':'array','items':{'type':'integer'}}},'required':['nested'],'additionalProperties':False}
    spec=ToolSpec(name='fixture',description='fixture description',parameters=parameters)
    registry=ToolRegistry();tool=registry.register(spec,handler)
    exported=registry.function_schemas()
    assert exported==[{'type':'function','function':{'name':'fixture','description':'fixture description','parameters':parameters}}]
    exported[0]['function']['parameters']['properties']['nested']['items']['type']='string'
    spec.parameters['properties']['nested']['items']['type']='boolean'
    assert registry.function_schemas()[0]['function']['parameters']['properties']['nested']['items']['type']=='integer'
    tool.validate_arguments({'nested':[1]})
    with pytest.raises(ToolBlockedError):tool.validate_arguments({'nested':['bad']})


def test_document_local_refs_and_dialect_survive_export():
    parameters={'$schema':'https://json-schema.org/draft/2020-12/schema','$defs':{'count':{'type':'integer','minimum':1}},'type':'object','properties':{'count':{'$ref':'#/$defs/count'}}}
    registry=ToolRegistry();tool=registry.register(ToolSpec(name='fixture',description='fixture',parameters=parameters),handler)
    assert registry.function_schemas()[0]['function']['parameters']==parameters
    tool.validate_arguments({'count':1})
    with pytest.raises(ToolBlockedError):tool.validate_arguments({'count':0})


def test_empty_schema_export_preserves_object_only_dispatch_boundary():
    registry=ToolRegistry();tool=registry.register(ToolSpec(name='fixture',description='fixture'),handler)
    assert registry.function_schemas()[0]['function']['parameters']=={'type':'object','properties':{}}
    tool.validate_arguments({'arbitrary':'allowed by empty schema'})
    with pytest.raises(ToolBlockedError):tool.validate_arguments([])


@pytest.mark.parametrize('key',['$ref','$dynamicRef','$recursiveRef'])
def test_remote_reference_never_enters_export_catalog(key):
    registry=ToolRegistry()
    with pytest.raises(ToolError,match='document-local'):
        registry.register(ToolSpec(name='fixture',description='fixture',parameters={key:'https://fixture.invalid/schema'}),handler)
    assert registry.function_schemas()==[]
