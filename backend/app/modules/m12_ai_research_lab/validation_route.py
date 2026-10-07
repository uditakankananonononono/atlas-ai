"""Safe validation diagnostics for the two model execution endpoints only."""
from fastapi.exceptions import RequestValidationError
from fastapi.routing import APIRoute
from starlette.responses import JSONResponse
from .response_json import safe_workflow_json

class ModelExecutionRoute(APIRoute):
    def get_route_handler(self):
        original=super().get_route_handler()
        if self.endpoint.__name__ not in ('run','run_workflow') or self.endpoint.__module__!='app.modules.m12_ai_research_lab.routes':
            return original
        async def handle(request):
            try:return await original(request)
            except RequestValidationError as error:
                # Input and ctx can carry NaN or private prompt/body content.
                # Preserve field/type/message evidence without echoing raw values.
                errors=[{key:item[key] for key in ('type','loc','msg') if key in item} for item in error.errors()]
                safe,invalid=safe_workflow_json(errors)
                detail={'errors':safe,'invalid_json_paths':invalid} if invalid else safe
                return JSONResponse(status_code=422,content={'detail':detail})
        return handle
