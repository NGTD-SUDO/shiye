"""认证相关请求/响应模型"""
from pydantic import BaseModel, Field


class WechatLoginRequest(BaseModel):
    code: str = Field(min_length=1, description="微信授权 code")


class DevLoginRequest(BaseModel):
    openid: str = Field(min_length=1, max_length=64, description="本地开发用任意标识")
    nickname: str | None = Field(default=None, max_length=100)
    invite_code: str | None = Field(default=None, description="内测邀请码（由发起人提供）")


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: int
    nickname: str


class UpdateMeRequest(BaseModel):
    nickname: str | None = Field(default=None, max_length=100)
    avatar_url: str | None = Field(default=None, max_length=500)
