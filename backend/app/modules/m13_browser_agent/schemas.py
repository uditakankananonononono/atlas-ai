from pydantic import BaseModel, ConfigDict, Field, field_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class NavigateIn(StrictModel):
    session_id: str = Field(min_length=1, max_length=120, pattern=r"^[A-Za-z0-9_.-]+$")
    url: str = Field(min_length=1, max_length=4096)
    persistent: bool = False


class SessionIn(StrictModel):
    session_id: str = Field(min_length=1, max_length=120, pattern=r"^[A-Za-z0-9_.-]+$")


class FieldIn(StrictModel):
    selector: str = Field(min_length=1, max_length=500)
    label: str = Field(default="", max_length=300)
    name: str = Field(default="", max_length=300)
    placeholder: str = Field(default="", max_length=300)
    input_type: str = Field(default="text", max_length=40)
    required: bool = False


class FillIn(StrictModel):
    session_id: str = Field(min_length=1, max_length=120, pattern=r"^[A-Za-z0-9_.-]+$")
    fields: list[FieldIn] = Field(max_length=200)
    data: dict[str, str] = Field(max_length=200)

    @field_validator("data")
    @classmethod
    def bounded_values(cls, data: dict[str, str]) -> dict[str, str]:
        if any(len(key) > 300 or len(value) > 10000 for key, value in data.items()):
            raise ValueError("form data is too large")
        return data


class SubmitIn(StrictModel):
    session_id: str = Field(min_length=1, max_length=120, pattern=r"^[A-Za-z0-9_.-]+$")
    selector: str = Field(min_length=1, max_length=500)
    values: dict[str, str] = Field(max_length=200)


class SubmitExecuteIn(SubmitIn):
    approval_id: str = Field(min_length=1, max_length=200)
