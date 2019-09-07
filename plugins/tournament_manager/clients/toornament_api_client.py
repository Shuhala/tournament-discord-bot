import datetime
import logging
from configparser import ConfigParser
from typing import List, Optional

import requests

logger = logging.getLogger(__name__)


class ToornamentAPIClient:
    def __init__(self, config_file: str = "config.ini"):
        self.token: Optional[dict] = None

        # load config
        config = ConfigParser()
        config.read(config_file)
        try:
            self.api_url = config["Toornament"]["TOORNAMENT_API_URL"]
            self.api_key = config["Toornament"]["TOORNAMENT_API_KEY"]
            self.client_id = config["Toornament"]["TOORNAMENT_CLIENT_ID"]
            self.client_secret = config["Toornament"]["TOORNAMENT_CLIENT_SECRET"]
        except KeyError:
            raise Exception("Could not load Toornament configuration")

    def get_tournament(self, tournament_id: int) -> Optional[dict]:
        """
        See: https://developer.toornament.com/v2/doc/organizer_tournaments#get:tournaments:id  # noqa
        """
        headers = self._get_headers(auth=True)
        url = f"{self.api_url}/organizer/v2/tournaments/{tournament_id}"

        return next(iter(self._get_full_result(url, headers)), {})

    def get_tournaments(self, params: Optional[dict] = None) -> List[dict]:
        """
        See: https://developer.toornament.com/v2/doc/organizer_tournaments#get:tournaments
        """
        if not params:
            params = {}

        headers = self._get_headers(auth=True, Range="tournaments=0-49")
        url = f"{self.api_url}/organizer/v2/tournaments"

        return self._get_full_result(url, headers, params)

    def get_participant(self, tournament_id: int, participant_id: int) -> Optional[dict]:
        """
        See: https://developer.toornament.com/v2/doc/organizer_tournaments#get:tournaments:id  # noqa
        """
        headers = self._get_headers(auth=True, scope="organizer:participant")
        url = (
            f"{self.api_url}/organizer/v2/tournaments/{tournament_id}"
            f"/participants/{participant_id}"
        )

        return next(iter(self._get_full_result(url, headers)), {})

    def get_match(self, tournament_id, match_id) -> Optional[dict]:
        headers = self._get_headers(scope="organizer:result", range="matches=0-99")
        url = f"{self.api_url}/viewer/v2/tournaments/{tournament_id}/matches/{match_id}"

        return next(iter(self._get_full_result(url, headers)), {})

    def get_matches(self, tournament_id, params: Optional[dict] = None) -> List[dict]:
        headers = self._get_headers(scope="organizer:result", range="matches=0-99")
        url = f"{self.api_url}/viewer/v2/tournaments/{tournament_id}/matches"

        return self._get_full_result(url, headers, params=params)

    def get_participants(
        self, tournament_id, params: Optional[dict] = None
    ) -> List[dict]:
        if not params:
            params = {"sort": "alphabetic"}

        headers = self._get_headers(Range="participants=0-49")
        url = f"{self.api_url}/viewer/v2/tournaments/{tournament_id}/participants"

        return self._get_full_result(url, headers, params=params)

    def _get_full_result(self, url, headers, params=None, result=None) -> List[dict]:
        if not params:
            params = {}
        if not result:
            result = []

        response = requests.get(url, headers=headers, params=params)

        # Standard response
        if response.status_code == 200:
            result.append(response.json())
        # Paginated response
        elif response.status_code == 206:
            result.extend(response.json())
            next_pagination = self._get_next_pagination(
                response.headers.get("Content-Range")
            )
            if next_pagination:
                headers.update({"Range": next_pagination})
                self._get_full_result(url, headers, params, result)
        else:
            logger.error(
                f"Can't retrieve list, code {response.status_code}: {response.content}"
            )

        return result

    def _get_headers(self, auth=False, scope=None, **kwargs) -> dict:
        headers = {
            "Content-Type": "application/json",
            "X-Api-Key": self.api_key,
            **kwargs,
        }

        if auth:
            token = self._get_access_token(scope)
            headers.update(
                {
                    "Authorization": f"{token.get('token_type')} "
                    f"{token.get('access_token')}"
                }
            )

        return headers

    def _get_access_token(self, scope: Optional[str] = None) -> dict:
        if not scope:
            scope = "organizer:view"
        now = datetime.datetime.now()

        if self.token:
            expires_in = self.token.get("expires_in")
            is_expired = self.token.get("timestamp") < now - datetime.timedelta(
                seconds=expires_in
            )
            if not is_expired:
                return self.token

        # we don't have a token or it's expired
        url = f"{self.api_url}/oauth/v2/token"
        headers = {"Content-Type": "application/x-www-form-urlencoded"}
        data = {
            "grant_type": "client_credentials",
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "scope": scope,
        }

        response = requests.post(url, headers=headers, data=data)

        if response.status_code == 200:
            token = response.json()
            token.update({"timestamp": now})
            return token

        logger.error("Failed to get access token: %s", response)
        raise Exception("Failed to get access token")

    @staticmethod
    def _get_next_pagination(content, increment_step=49):
        if not content:
            logger.error(f"invalid content provided for get_next_pagination: {content}")
            return None

        content_type, content_size = content.split(" ")
        content_range, total = content_size.split("/")
        lower_bound, upper_bound = content_range.split("-")

        if int(upper_bound) < int(total):
            lower_bound = int(upper_bound) + 1
            if lower_bound == int(total):
                return None

            upper_bound = int(upper_bound) + increment_step
            if upper_bound > int(total):
                upper_bound = int(total)

            return f"{content_type}={lower_bound}-{upper_bound}"

        return None
