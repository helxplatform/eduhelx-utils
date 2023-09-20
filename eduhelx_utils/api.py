"""
An API wrapper for the Eduhelx Grader API.

Refer to Grader API /docs for full documentation on API endpoints.
"""

import jwt
import time
import httpx
from .git import get_commit_info
from ._version import __version__

class APIException(Exception):
    def __init__(self, response, message):
        super().__init__(message)
        self.response = response

class UnauthorizedException(APIException):
    pass

class ForbiddenException(APIException):
    pass

class Api:
    def __init__(
            self,
            api_url: str,
            user_onyen: str,
            user_autogen_password: str,
            jwt_refresh_leeway_seconds: int = 60
        ):
        self.api_url = api_url
        self.user_onyen = user_onyen
        self.user_autogen_password = user_autogen_password
        self.jwt_refresh_leeway_seconds = jwt_refresh_leeway_seconds

        self._access_token = None
        self.access_token_exp = None
        self._refresh_token = None
        self.refresh_token_exp = None
        self.client = httpx.AsyncClient(
            base_url=f"{ self.api_url }api/v1/",
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
        self.access_token_exp = jwt.decode(self._access_token, options={"verify_signature": False})["exp"]

    @property
    def refresh_token(self) -> str | None:
        return self._refresh_token

    @refresh_token.setter
    def refresh_token(self, value: str | None):
        self._refresh_token = value
        self.refresh_token_exp = jwt.decode(self._refresh_token, options={"verify_signature": False})["exp"]


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
        res = await self._post("login", verify_credentials=False, json={
            "onyen": self.user_onyen,
            "autogen_password": self.user_autogen_password
        })
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
    

    """ Submissions """
    async def get_my_submissions(self, assignment_id: int):
        return await self._get("submissions/self", params={
            "assignment_id": assignment_id
        })
    
    async def get_latest_submission(self, onyen: str, assignment_id: int):
        return await self._get("latest_submission", params={
            "onyen": onyen,
            "assignment_id": assignment_id
        })

    async def create_submission(self, assignment_id: str, commit_id: str):
        return await self._post("submission", json={
            "assignment_id": assignment_id,
            "commit_id": commit_id
        })
    
    
    """ Assignments """
    async def get_my_assignments(self):
        return await self._get("assignments/self")
    
    async def update_assignment(self):
        ...
    
    
    """ Users """
    async def get_my_user(self):
        return await self._get("student/self")
    
    
    """ Students """
    async def get_student(self, onyen: str):
        return await self._get(f"student/{onyen}")
    
    async def list_students(self):
        return await self._get("students")
    
    async def create_student(self, onyen: str, first_name: str, last_name: str, email: str):
        return await self._post("student", json={
            "onyen": onyen,
            "first_name": first_name,
            "last_name": last_name,
            "email": email
        })
    

    """ Instructors """
    async def get_instructor(self, onyen: str):
        return await self._get(f"instructor/{onyen}")
    
    async def list_instructors(self):
        return await self._get("instructors")
    
    async def create_instructor(self, onyen: str, first_name: str, last_name: str, email: str):
        return await self._post("instructor", json={
            "onyen": onyen,
            "first_name": first_name,
            "last_name": last_name,
            "email": email
        })
    
    
    """ Course """
    async def get_course(self):
        return await self._get("course")
    

    """
    async def get_assignment_submissions(self, assignment_id: int, git_path="./"):
        submissions = await self._get("submissions/self", params={
            "assignment_id": assignment_id
        })
        for submission in submissions:
            submission["commit"] = get_commit_info(submission["commit_id"], path=git_path)
        
        return submissions
    """
