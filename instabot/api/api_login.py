import json
import os
import random
import time
import traceback

import requests
import requests.utils

from . import config, devices

# ====== SYNC METHODS ====== #


def sync_device_features(self, login=None):
    data = {
        "id": self.uuid,
        "server_config_retrieval": "1",
        "experiments": config.LOGIN_EXPERIMENTS,
    }
    if login is False:
        data["id"] = self.user_id
        data["_uuid"] = self.uuid
        data["_uid"] = self.user_id
        data["_csrftoken"] = self.token
    data = json.dumps(data)
    self.last_experiments = time.time()
    return self.send_request(
        "qe/sync/", data, login=login, headers={"X-DEVICE-ID": self.uuid}
    )


def sync_launcher(self, login=None):
    data = {
        "id": self.uuid,
        "server_config_retrieval": "1",
    }
    if login is False:
        data["_uid"] = self.user_id
        data["_uuid"] = self.uuid
        data["_csrftoken"] = self.token
    data = json.dumps(data)
    return self.send_request("launcher/sync/", data, login=login)


def set_contact_point_prefill(self, usage=None, login=False):
    data = {
        "phone_id": self.phone_id,
        "usage": usage,
    }
    if login is False:
        data["_csrftoken"] = self.token
    data = json.dumps(data)
    return self.send_request("accounts/contact_point_prefill/", data, login=True)


# "android_device_id":"android-f14b9731e4869eb",
# "phone_id":"b4bd7978-ca2b-4ea0-a728-deb4180bd6ca",
# "usages":"[\"account_recovery_omnibox\"]",
# "_csrftoken":"9LZXBXXOztxNmg3h1r4gNzX5ohoOeBkI",
# "device_id":"70db6a72-2663-48da-96f5-123edff1d458"
def get_prefill_candidates(self, login=False):
    data = {
        "android_device_id": self.device_id,
        "phone_id": self.phone_id,
        "usages": '["account_recovery_omnibox"]',
        "device_id": self.uuid,
    }
    if login is False:
        data["_csrftoken"] = self.token
        data["client_contact_points"] = (
            f'["type":"omnistring","value":"{self.username}","source":"last_login_attempt"]',
        )
    data = json.dumps(data)
    return self.send_request("accounts/get_prefill_candidates/", data, login=login)


def get_account_family(self):
    return self.send_request("multiple_accounts/get_account_family/")


def get_zr_token_result(self):
    url = (
        "zr/token/result/?device_id={rank_token}"
        "&token_hash=&custom_device_id={custom_device_id}&fetch_reason=token_expired"
    )
    url = url.format(rank_token=self.device_id, custom_device_id=self.uuid)
    return self.send_request(url)


def banyan(self):
    url = 'banyan/banyan/?views=["story_share_sheet","threads_people_picker","group_stories_share_sheet","reshare_share_sheet"]'
    return self.send_request(url)


def igtv_browse_feed(self):
    url = "igtv/browse_feed/?prefetch=1"
    return self.send_request(url)


def creatives_ar_class(self):
    data = {
        "_csrftoken": self.token,
        "_uuid": self.uuid,
    }
    data = json.dumps(data)
    return self.send_request("creatives/ar_class/", data)


# ====== LOGIN/PRE FLOWS METHODS ====== #


def pre_login_flow(self):
    self.logger.info("Not yet logged in starting: PRE-LOGIN FLOW!")
    # /api/v1/accounts/contact_point_prefill/
    self.set_contact_point_prefill("prefill", True)

    # /api/v1/qe/sync (server_config_retrieval)
    self.sync_device_features(True)

    # /api/v1/launcher/sync/ (server_config_retrieval)
    self.sync_launcher(True)

    # /api/v1/accounts/get_prefill_candidates
    self.get_prefill_candidates(True)


# DO NOT MOVE ANY OF THE ENDPOINTS THEYRE IN THE CORRECT ORDER
def login_flow(self, just_logged_in=False, app_refresh_interval=1800):
    self.last_experiments = time.time()
    self.logger.info(f"LOGIN FLOW! Just logged-in: {just_logged_in}")
    check_flow = []
    if just_logged_in:
        try:
            check_flow.extend(
                (
                    self.sync_launcher(False),
                    self.get_account_family(),
                    self.get_zr_token_result(),
                    self.sync_device_features(False),
                    self.banyan(),
                    self.creatives_ar_class(),
                    self.get_reels_tray_feed(reason="cold_start"),
                    self.get_timeline_feed(),
                    self.push_register(),
                    self.media_blocked(),
                    self.get_loom_fetch_config(),
                    self.get_news_inbox(),
                    self.get_business_branded_content(),
                    self.get_scores_bootstrap(),
                    self.get_monetization_products_eligibility_data(),
                    self.get_linked_accounts(),
                    self.get_cooldowns(),
                    self.push_register(),
                    self.arlink_download_info(),
                    self.get_username_info(self.user_id),
                    self.get_presence(),
                    self.get_direct_v2_inbox2(),
                    self.topical_explore(),
                    self.get_direct_v2_inbox(),
                    self.notification_badge(),
                    self.facebook_ota(),
                )
            )
        except Exception as e:
            self.logger.error(f"Exception raised: {e}\n{traceback.format_exc()}")
            return False
    else:
        try:
            pull_to_refresh = random.randint(1, 100) % 2 == 0
            check_flow.extend(
                (
                    self.get_timeline_feed(
                        options=["is_pull_to_refresh"]
                        if pull_to_refresh
                        else []
                    ),
                    self.get_reels_tray_feed(
                        reason="pull_to_refresh"
                        if pull_to_refresh
                        else "cold_start"
                    ),
                )
            )
            is_session_expired = (time.time() - self.last_login) > app_refresh_interval
            if is_session_expired:
                self.last_login = time.time()
                self.client_session_id = self.generate_UUID(uuid_type=True)

                check_flow.extend(
                    (
                        self.get_ranked_recipients("reshare", True),
                        self.get_ranked_recipients("save", True),
                        self.get_inbox_v2(),
                        self.get_presence(),
                        self.get_recent_activity(),
                        self.get_profile_notice(),
                        self.explore(False),
                    )
                )
            if (time.time() - self.last_experiments) > 7200:
                check_flow.append(self.sync_device_features())
        except Exception as e:
            self.logger.error(
                f"Error loginin, exception raised: {e}\n{traceback.format_exc()}"
            )
            return False

    self.save_uuid_and_cookie()
    return False not in check_flow


# ====== DEVICE / CLIENT_ID / PHONE_ID AND OTHER VALUES (uuids) ====== #


def set_device(self):
    self.device_settings = devices.DEVICES[self.device]
    self.user_agent = config.USER_AGENT_BASE.format(**self.device_settings)


def generate_all_uuids(self):
    self.phone_id = self.generate_UUID(uuid_type=True)
    self.uuid = self.generate_UUID(uuid_type=True)
    self.client_session_id = self.generate_UUID(uuid_type=True)
    self.advertising_id = self.generate_UUID(uuid_type=True)
    self.device_id = self.generate_device_id(
        self.get_seed(self.username, self.password)
    )


def reinstall_app_simulation(self):
    self.logger.info("Reinstall app simulation, generating new `phone_id`...")
    self.phone_id = self.generate_UUID(uuid_type=True)
    self.save_uuid_and_cookie()
    self.logger.info(f"New phone_id: {self.phone_id}")


def change_device_simulation(self):
    self.logger.info("Change device simulation")
    self.reinstall_app_simulation()
    self.logger.info("Generating new `android_device_id`...")
    self.device_id = self.generate_device_id(
        self.get_seed(self.generate_UUID(uuid_type=True))
    )
    self.save_uuid_and_cookie()
    self.logger.info(f"New android_device_id: {self.device_id}")


def load_uuid_and_cookie(self, load_uuid=True, load_cookie=True):
    if self.cookie_fname is None:
        fname = f"{self.username}_uuid_and_cookie.json"
        self.cookie_fname = os.path.join(self.base_path, fname)
        print(os.path.join(self.base_path, fname))

    if os.path.isfile(self.cookie_fname) is False:
        return False

    with open(self.cookie_fname, "r") as f:
        data = json.load(f)
        if "cookie" in data:
            self.last_login = data["timing_value"]["last_login"]
            self.last_experiments = data["timing_value"]["last_experiments"]

            if load_cookie:
                self.logger.debug("Loading cookies")
                self.session.cookies = requests.utils.cookiejar_from_dict(
                    data["cookie"]
                )
                cookie_username = self.cookie_dict["ds_user"]
                assert cookie_username == self.username.lower()
                self.cookie_dict["urlgen"]

            if load_uuid:
                self.logger.debug("Loading uuids")
                self.phone_id = data["uuids"]["phone_id"]
                self.uuid = data["uuids"]["uuid"]
                self.client_session_id = data["uuids"]["client_session_id"]
                self.advertising_id = data["uuids"]["advertising_id"]
                self.device_id = data["uuids"]["device_id"]

                self.device_settings = data["device_settings"]
                self.user_agent = data["user_agent"]

            msg = (
                "Recovery from {}: COOKIE {} - UUIDs {} - TIMING, DEVICE "
                "and ...\n- user-agent={}\n- phone_id={}\n- uuid={}\n- "
                "client_session_id={}\n- device_id={}"
            )

            self.logger.info(
                msg.format(
                    self.cookie_fname,
                    load_cookie,
                    load_uuid,
                    self.user_agent,
                    self.phone_id,
                    self.uuid,
                    self.client_session_id,
                    self.device_id,
                )
            )
        else:
            self.logger.info(
                "The cookie seems to be the with the older structure. "
                "Load and init again all uuids"
            )
            self.session.cookies = requests.utils.cookiejar_from_dict(data)
            self.last_login = time.time()
            self.last_experiments = time.time()
            cookie_username = self.cookie_dict["ds_user"]
            assert cookie_username == self.username
            self.set_device()
            self.generate_all_uuids()

    self.is_logged_in = True
    return True


def save_uuid_and_cookie(self):
    if self.cookie_fname is None:
        fname = f"{self.username}_uuid_and_cookie.json"
        self.cookie_fname = os.path.join(self.base_path, fname)

    data = {
        "uuids": {
            "phone_id": self.phone_id,
            "uuid": self.uuid,
            "client_session_id": self.client_session_id,
            "advertising_id": self.advertising_id,
            "device_id": self.device_id,
        },
        "cookie": requests.utils.dict_from_cookiejar(self.session.cookies),
        "timing_value": {
            "last_login": self.last_login,
            "last_experiments": self.last_experiments,
        },
        "device_settings": self.device_settings,
        "user_agent": self.user_agent,
    }
    with open(self.cookie_fname, "w") as f:
        json.dump(data, f)
