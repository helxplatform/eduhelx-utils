"""
An API wrapper for the Eduhelx Grader API.

Refer to Grader API /docs for full documentation on API endpoints.
"""

import jwt
import time
import httpx
from enum import Enum
from ._version import __version__

class AuthType(Enum):
    APPSTORE_INSTRUCTOR = "appstore:instructor"
    APPSTORE_STUDENT = "appstore:student"
    PASSWORD = "password"

class APIException(Exception):
    def __init__(self, response, message):
        super().__init__(message)
        self.response = response

    @property
    def data(self):
        return self.response.json()

    @property
    def error_code(self) -> str:
        return self.data["error_code"]

class UnauthorizedException(APIException):
    pass

class ForbiddenException(APIException):
    pass

class Api:
    def __init__(
            self,
            api_url: str,
            user_onyen: str,
            # Uses appstore auth if None
            user_autogen_password: str = None,
            auth_type: AuthType = AuthType.PASSWORD,
            appstore_access_token: str = None,
            jwt_refresh_leeway_seconds: int = 60
        ):
        self.api_url = api_url
        self.user_onyen = user_onyen
        self.user_autogen_password = user_autogen_password
        self.auth_type = auth_type
        self.appstore_access_token = appstore_access_token
        self.jwt_refresh_leeway_seconds = jwt_refresh_leeway_seconds

        self._access_token = None
        self.access_token_exp = None
        self._refresh_token = None
        self.refresh_token_exp = None
        self.client = httpx.AsyncClient(
            base_url=f"{ self.api_url }{ '/' if not self.api_url.endswith('/') else '' }api/v1/",
            headers={
                "User-Agent": f"eduhelx_utils/{__version__}"
            }
        )

    @property
    def access_token(self) -> str | None:
        return self._access_token

    @access_token.setter
    def access_token(self, value: str | None):
        self._access_token = value
        if value is not None:
            self.access_token_exp = jwt.decode(self._access_token, options={"verify_signature": False})["exp"]
        else:
            self.access_token_exp = None

    @property
    def refresh_token(self) -> str | None:
        return self._refresh_token

    @refresh_token.setter
    def refresh_token(self, value: str | None):
        self._refresh_token = value
        if value is not None:
            self.refresh_token_exp = jwt.decode(self._refresh_token, options={"verify_signature": False})["exp"]
        else:
            self.refresh_token_exp = None


    """ Internal """
    async def _ensure_access_token(self):
        if (
            self.refresh_token is None
            or self.refresh_token_exp is None
            or self.refresh_token_exp - time.time() <= self.jwt_refresh_leeway_seconds
        ):
            await self._login()

        elif (
            self.access_token is None
            or self.access_token_exp is None
            or self.access_token_exp - time.time() <= self.jwt_refresh_leeway_seconds  
        ):
            await self._refresh_access_token()

    async def _handle_response(self, response: httpx.Response):
        if response.status_code == 200:
            return response.json()
        elif response.status_code == 401:
            self.access_token = None
            raise UnauthorizedException(response, "You aren't logged in")
        elif response.status_code == 403:
            raise ForbiddenException(response, "You lack the permission to make this API request")
        else:
            raise APIException(response, f"API request to { response.request.url } failed with status code { response.status_code } { response.text }")

    async def _make_request(self, method: str, endpoint: str, verify_credentials=True, headers={}, **kwargs):
        if verify_credentials: await self._ensure_access_token()
        res = await self.client.request(
            method,
            endpoint,
            headers={
                **({"Authorization": f"Bearer { self.access_token }"} if self.access_token is not None else {}),
                **headers
            },
            **kwargs
        )
        return await self._handle_response(res)

    async def _get(self, endpoint: str, **kwargs):
        return await self._make_request("GET", endpoint, **kwargs)

    async def _post(self, endpoint: str, **kwargs):
        return await self._make_request("POST", endpoint, **kwargs)
    
    async def _put(self, endpoint: str, **kwargs):
        return await self._make_request("PUT", endpoint, **kwargs)
    
    async def _patch(self, endpoint: str, **kwargs):
        return await self._make_request("PATCH", endpoint, **kwargs)
    
    async def _delete(self, endpoint: str, **kwargs):
        return await self._make_request("DELETE", endpoint, **kwargs)
            

    """ Auth """
    # This is an API endpoint; it is marked as private because auth is handled internally.
    async def _login(self):
        if self.auth_type == AuthType.PASSWORD:
            res = await self._post("login", verify_credentials=False, json={
                "onyen": self.user_onyen,
                "autogen_password": self.user_autogen_password
            })
        elif self.auth_type in (AuthType.APPSTORE_INSTRUCTOR, AuthType.APPSTORE_STUDENT):
            _, user_type = self.auth_type.value.split(":")
            res = await self._post("login/appstore", verify_credentials=False, json={
                "user_type": user_type
            }, headers={ "APPSTORE-ACCESS-TOKEN": self.appstore_access_token })
        self.access_token = res.get("access_token")
        self.refresh_token = res.get("refresh_token")

    # This is an API endpoint; it is marked as private because auth is handled internally.
    async def _refresh_access_token(self):
        try:
            self.access_token = await self._post("refresh", verify_credentials=False, json={
                "refresh_token": self.refresh_token
            })
        except:
            self.access_token = None
            self.refresh_token = None

    async def get_my_role(self):
        return await self._get("role/self")
    
    async def set_ssh_key(self, name: str, key: str):
        return await self._put("login/gitea/ssh", json={
            "name": name,
            "key": key
        })

    async def remove_ssh_key(self, key_name: str):
        return await self._delete("login/gitea/ssh", params={
            "key_name": key_name
        })
    

    """ Submissions """
    async def get_submissions(self, assignment_id: int, student_onyen: str | None=None):
        params = {
            "assignment_id": assignment_id
        }
        if student_onyen is not None: params["student_onyen"] = student_onyen
        return await self._get("submissions", params=params)
    
    async def get_my_submissions(self, assignment_id: int):
        return await self._get("submissions/self", params={
            "assignment_id": assignment_id
        })
    
    async def get_submission(self, submission_id: int):
        return await self._get(f"submissions/{ submission_id }")
    
    async def get_active_submission(self, onyen: str, assignment_id: int):
        return await self._get("submissions/active", params={
            "onyen": onyen,
            "assignment_id": assignment_id
        })

    async def create_submission(self, assignment_id: int, commit_id: str):
        return await self._post("submissions", json={
            "assignment_id": assignment_id,
            "commit_id": commit_id
        })
    
    async def download_submission(self, submission_id: int):
        return await self._get(f"submissions/{ submission_id }/download")
    
    async def download_active_submission(self, onyen: str, assigment_id: int):
        return await self._get("submissions/active/download", params={
            "onyen": onyen,
            "assignment_id": assigment_id
        })
    
    
    """ Assignments """
    async def get_my_assignments(self):
        return await self._get("assignments/self")
    
    async def update_assignment(self, name: str, **patch_fields):
        return await self._patch(f"assignments/{name}", json=patch_fields)
    
    async def grade_assignment(self, name: str, master_notebook_content: str, otter_config_content: str):
        return await self._post(f"assignments/{name}/grade", json={
            "master_notebook_content": master_notebook_content,
            "otter_config_content": otter_config_content
        })
    
    
    """ Users """
    async def get_my_user(self):
        return await self._get("users/self")
    
    async def get_ldap_user_info(self, pid: str):
        return await self._get(f"users/{pid}/ldap")
    
    
    """ Students """
    async def get_student(self, onyen: str):
        return await self._get(f"students/{onyen}")
    
    async def list_students(self):
        return await self._get("students")
    
    async def create_student(self, onyen: str, first_name: str, last_name: str, email: str):
        return await self._post("students", json={
            "onyen": onyen,
            "first_name": first_name,
            "last_name": last_name,
            "email": email
        })
    
    async def mark_my_fork_as_cloned(self):
        return await self._put("students/self/fork_cloned")

    """ Instructors """
    async def get_instructor(self, onyen: str):
        return await self._get(f"instructors/{onyen}")
    
    async def list_instructors(self):
        return await self._get("instructors")
    
    async def create_instructor(self, onyen: str, first_name: str, last_name: str, email: str):
        return await self._post("instructors", json={
            "onyen": onyen,
            "first_name": first_name,
            "last_name": last_name,
            "email": email
        })
    
    
    """ Course """
    async def get_course(self):
        return await self._get("course")
    

    """ LMS """
    async def lms_downsync(self):
        return await self._post("lms/downsync")
    
    """ Settings """
    async def get_settings(self):
        return await self._get("settings")