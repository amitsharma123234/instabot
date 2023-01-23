from tqdm import tqdm
import time


def unfollow(self, user_id):
    user_id = self.convert_to_user_id(user_id)
    user_info = self.get_user_info(user_id)

    if not user_info:
        self.logger.info(f"Can't get user_id={str(user_id)} info")
        return False  # No user_info

    username = user_info.get("username")

    if self.log_follow_unfollow:
        msg = f"Going to unfollow `user_id` {user_id} with username {username}."
        self.logger.info(msg)
    else:
        self.console_print(
            f"===> Going to unfollow `user_id`: {user_id} with username: {username}"
        )

    if self.check_user(user_id, unfollowing=True):
        return True  # whitelisted user
    if not self.reached_limit("unfollows"):
        if self.blocked_actions["unfollows"]:
            self.logger.warning("YOUR `UNFOLLOW` ACTION IS BLOCKED")
            if self.blocked_actions_protection:
                self.logger.warning(
                    "blocked_actions_protection ACTIVE. " "Skipping `unfollow` action."
                )
                return False
        self.delay("unfollow")
        _r = self.api.unfollow(user_id)
        if _r == "feedback_required":
            self.logger.error("`Unfollow` action has been BLOCKED...!!!")
            if self.blocked_actions_sleep:
                if (
                    self.sleeping_actions["unfollows"]
                    and self.blocked_actions_protection
                ):
                    self.logger.warning(
                        "This is the second blocked \
                        `Unfollow` action."
                    )
                    self.logger.warning(
                        "Activating blocked actions \
                        protection for `Unfollow` action."
                    )
                    self.sleeping_actions["unfollows"] = False
                    self.blocked_actions["unfollows"] = True
                else:
                    self.logger.info(
                        "`Unfollow` action is going to sleep \
                        for %s seconds."
                        % self.blocked_actions_sleep_delay
                    )
                    self.sleeping_actions["unfollows"] = True
                    time.sleep(self.blocked_actions_sleep_delay)
            elif self.blocked_actions_protection:
                self.logger.warning(
                    "Activating blocked actions \
                        protection for `Unfollow` action."
                )
                self.blocked_actions["unfollows"] = True
            return False
        if _r:
            if self.log_follow_unfollow:
                msg = f"Unfollowed `user_id` {user_id} with username {username}"
                self.logger.info(msg)
            else:
                msg = "===> Unfollowed, `user_id`: {}, user_name: {}"
                self.console_print(msg.format(user_id, username), "yellow")
            self.unfollowed_file.append(user_id)
            self.total["unfollows"] += 1
            if user_id in self.following:
                self.following.remove(user_id)
            if self.blocked_actions_sleep and self.sleeping_actions["unfollows"]:
                self.logger.info("`Unfollow` action is no longer sleeping.")
                self.sleeping_actions["unfollows"] = False
            return True
    else:
        self.logger.info("Out of unfollows for today.")
    return False


def unfollow_users(self, user_ids):
    broken_items = []
    self.logger.info(f"Going to unfollow {len(user_ids)} users.")
    user_ids = set(map(str, user_ids))
    filtered_user_ids = list(set(user_ids) - set(self.whitelist))
    if len(filtered_user_ids) != len(user_ids):
        self.logger.info(
            f"After filtration by whitelist {len(filtered_user_ids)} users left."
        )
    for user_id in tqdm(filtered_user_ids, desc="Processed users"):
        if not self.unfollow(user_id):
            self.error_delay()
            i = filtered_user_ids.index(user_id)
            broken_items = filtered_user_ids[i:]
            break
    self.logger.info(f'DONE: Total unfollowed {self.total["unfollows"]} users.')
    return broken_items


def unfollow_non_followers(self, n_to_unfollows=None):
    self.logger.info("Unfollowing non-followers.")
    self.console_print(" ===> Start unfollowing non-followers <===", "red")
    non_followers = set(self.following) - set(self.followers) - self.friends_file.set
    non_followers = list(non_followers)
    for user_id in tqdm(non_followers[:n_to_unfollows]):
        if self.reached_limit("unfollows"):
            self.logger.info("Out of unfollows for today.")
            break
        self.unfollow(user_id)
    self.console_print(" ===> Unfollow non-followers done! <===", "red")


def unfollow_everyone(self):
    self.unfollow_users(self.following)
