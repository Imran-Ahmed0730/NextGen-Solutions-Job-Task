from typing import Annotated

from pydantic import BaseModel, ConfigDict, StringConstraints

SettingKey = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]


class CompanySettingCreate(BaseModel):
    key: SettingKey
    value: str = ""


class CompanySettingUpdate(BaseModel):
    value: str


class CompanySettingResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    key: str
    value: str


class CompanyBrandingResponse(BaseModel):
    company_name: str
    company_logo_path: str
    company_favicon_path: str
