import requests
import fnmatch
import sys
import os
import time
import logging
from urllib.parse import urljoin

logger = logging.getLogger("filterarr")


def get_env_var(name, default=None, required=False):
    val = os.environ.get(name, default)
    if val is None and required:
        logger.error(f"Environment variable '{name}' is required.")
        sys.exit(1)
    return val


def qb_login(session, url, username, password):
    resp = session.post(
        urljoin(url, "/api/v2/auth/login"), data={"username": username, "password": password}
    )
    return resp.ok


def get_qb_torrents(session, url):
    resp = session.get(urljoin(url, "/api/v2/torrents/info"))
    resp.raise_for_status()
    return resp.json()


def get_qb_torrent_files(session, url, hash_):
    resp = session.get(urljoin(url, f"/api/v2/torrents/files?hash={hash_}"))
    resp.raise_for_status()
    return resp.json()


def delete_qb_torrent(session, url, hash_):
    resp = session.post(
        urljoin(url, "/api/v2/torrents/delete"), data={"hashes": hash_, "deleteFiles": True}
    )
    resp.raise_for_status()
    return resp.ok


def get_file_extension(fname):
    return os.path.splitext(fname)[1].lower()


def match_blacklist(files, patterns):
    """
    Returns (True, file) if any file extension matches one of the patterns.
    Only compares against the **file's extension**. Pattern wildcards supported.
    """
    for file in files:
        fname = file["name"]
        ext = get_file_extension(fname)
        for pat in patterns:
            if fnmatch.fnmatch(ext, pat.lstrip("*")):  # *.r* pattern -> .r*
                return True, fname
    return False, None


def mark_sonarr_history_id_as_failed(sonarr_url, api_key, history_id):
    url = urljoin(sonarr_url, f"/api/v3/history/failed/{history_id}")
    try:
        resp = requests.post(url, headers={"X-Api-Key": api_key})
        if resp.ok:
            logger.debug(f"> Marked as failed in Sonarr: history id {history_id}")
        else:
            logger.error(f"> Sonarr failed to mark id {history_id} as failed: {resp.text}")
        return resp.ok
    except Exception as e:
        logger.error(f"Error marking as failed in Sonarr: {e}")
        return False


def mark_radarr_history_id_as_failed(radarr_url, api_key, history_id):
    url = urljoin(radarr_url, f"/api/v3/history/failed/{history_id}")
    try:
        resp = requests.post(url, headers={"X-Api-Key": api_key})
        if resp.ok:
            logger.debug(f"> Marked as failed in Radarr: history id {history_id}")
        else:
            logger.error(f"> Radarr failed to mark id {history_id} as failed: {resp.text}")
        return resp.ok
    except Exception as e:
        logger.error(f"Error marking as failed in Radarr: {e}")
        return False


def get_paged_grab_history(url, api_key, type_name):
    headers = {"X-Api-Key": api_key}
    records = []
    page = 1
    page_size = 100
    while True:
        params = {"page": page, "pageSize": page_size, "eventType": [1]}
        resp = requests.get(url, headers=headers, params=params)
        resp.raise_for_status()
        data = resp.json()
        recs = data["records"]
        if not recs:
            break
        records.extend(recs)
        if len(recs) < page_size:
            break
        page += 1
    logger.debug(f"{type_name}: {len(records)} history records found.")
    return records


def get_sonarr_history(sonarr_url, api_key):
    url = urljoin(sonarr_url, "/api/v3/history")
    return get_paged_grab_history(url, api_key, "Sonarr")


def get_radarr_history(radarr_url, api_key):
    url = urljoin(radarr_url, "/api/v3/history")
    return get_paged_grab_history(url, api_key, "Radarr")


def main(
    session,
    qb_host,
    qb_port,
    sonarr_host,
    sonarr_port,
    sonarr_api,
    radarr_host,
    radarr_port,
    radarr_api,
    blacklisted_extensions,
):
    qb_url = f"http://{qb_host}:{qb_port}"
    sonarr_url = f"http://{sonarr_host}:{sonarr_port}"
    radarr_url = f"http://{radarr_host}:{radarr_port}"

    logger.debug("Fetching qBittorrent torrents...")
    torrents = get_qb_torrents(session, qb_url)
    logger.debug("Fetching Sonarr/Radarr histories...")
    try:
        sonarr_hist = get_sonarr_history(sonarr_url, sonarr_api)
    except Exception as e:
        logger.warning(f"Warning: could not fetch Sonarr history: {e}")
        sonarr_hist = []
    try:
        radarr_hist = get_radarr_history(radarr_url, radarr_api)
    except Exception as e:
        logger.warning(f"Warning: could not fetch Radarr history: {e}")
        radarr_hist = []
    sonarr_hashes = {entry.get("downloadId", "").lower(): entry for entry in sonarr_hist}
    radarr_hashes = {entry.get("downloadId", "").lower(): entry for entry in radarr_hist}
    any_match = False
    logger.debug("Checking torrents...")
    for torrent in torrents:
        cat = (torrent.get("category") or "").lower()
        if cat not in ["tv-sonarr", "radarr"]:
            continue
        files = get_qb_torrent_files(session, qb_url, torrent["hash"])
        matched, bad_file = match_blacklist(files, blacklisted_extensions)
        if matched:
            any_match = True
            logger.info(
                f"> Found blacklisted file {bad_file} in {torrent['name']}! Deleting torrent."
            )
            delete_qb_torrent(session, qb_url, torrent["hash"])
            info_hash = torrent["hash"].lower()
            if cat == "tv-sonarr":
                sonarr_entry = sonarr_hashes.get(info_hash)
                if sonarr_entry:
                    mark_sonarr_history_id_as_failed(sonarr_url, sonarr_api, sonarr_entry.get("id"))
                else:
                    logger.warning(f"> No Sonarr grabbed-history found for {torrent['name']}")
            elif cat == "radarr":
                radarr_entry = radarr_hashes.get(info_hash)
                if radarr_entry:
                    mark_radarr_history_id_as_failed(radarr_url, radarr_api, radarr_entry.get("id"))
                else:
                    logger.warning(f"> No Radarr grabbed-history found for {torrent['name']}")
    return any_match


if __name__ == "__main__":
    import os

    qb_host = get_env_var("QB_HOST", "localhost")
    qb_port = get_env_var("QB_PORT", "8089")
    qb_user = get_env_var("QB_USER", "admin")
    qb_pass = get_env_var("QB_PASS", "adminadmin")
    sonarr_host = get_env_var("SONARR_HOST", required=True)
    sonarr_port = get_env_var("SONARR_PORT", required=True)
    sonarr_api = get_env_var("SONARR_API", required=True)
    radarr_host = get_env_var("RADARR_HOST", required=True)
    radarr_port = get_env_var("RADARR_PORT", required=True)
    radarr_api = get_env_var("RADARR_API", required=True)
    interval = int(get_env_var("POLLING_INTERVAL", 600))
    LOG_LEVEL = get_env_var("LOG_LEVEL", "INFO").upper()

    logger.setLevel(LOG_LEVEL)
    logger.addHandler(logging.StreamHandler())

    ext_str = get_env_var("BLACKLISTED_EXTENSIONS", ".r*,.zip*,.lnk,.arj")
    blacklisted_extensions = [x.strip() for x in ext_str.split(",") if x.strip()]
    logger.info(f"filterarr will run every {interval} seconds.")
    logger.info(f"Blacklisted extensions: {blacklisted_extensions}\n")

    session = requests.Session()

    qb_url = f"http://{qb_host}:{qb_port}"
    logger.debug("Logging in to qBittorrent...")
    if not qb_login(session, qb_url, qb_user, qb_pass):
        logger.error("qBittorrent login failed!")
        sys.exit(1)

    logger.debug("Successfully logged in to qBittorrent!")

    valid_logged = False

    try:
        while True:
            start = time.time()
            try:
                res = main(
                    session,
                    qb_host,
                    qb_port,
                    sonarr_host,
                    sonarr_port,
                    sonarr_api,
                    radarr_host,
                    radarr_port,
                    radarr_api,
                    blacklisted_extensions,
                )
                if res:
                    valid_logged = False
                if not valid_logged:
                    logger.info("All torrents are valid!")
                    valid_logged = True
            except requests.HTTPError as httpe:
                if "403" in str(httpe):
                    logger.debug("qBittorrent needs re-auth")
                    session = requests.Session()
                    if not qb_login(session, qb_url, qb_user, qb_pass):
                        logger.error("qBittorrent login failed! Retrying...")
            except Exception as e:
                logger.error("Unhandled error:", e)
            elapsed = time.time() - start
            if interval > 0:
                to_sleep = max(0, interval - elapsed)
                if to_sleep:
                    logger.debug(f"Waiting {int(to_sleep)} seconds for next scan...\n")
                    time.sleep(to_sleep)
            else:
                break
    finally:
        session.close()
