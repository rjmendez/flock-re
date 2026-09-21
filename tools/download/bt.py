#!/usr/bin/env python3
"""Fetch the DDoSecrets 'Flock ALPR camera' torrent.

Peer-network sources (DHT + trackers) plus data.ddosecrets.org as a web seed:
the torrent has no built-in web seeds, and the HTTP mirror's paths map onto the
torrent layout.
"""
import os, sys, time, datetime, libtorrent as lt

D = "/home/rjmendez/flock-alpr"
RESUME = os.path.join(D, "resume.fastresume")
WEB_SEED = "https://data.ddosecrets.org/"

ses = lt.session({
    "listen_interfaces": "0.0.0.0:6881,[::]:6881",
    "enable_dht": True, "enable_lsd": True,
    "enable_upnp": True, "enable_natpmp": True,
    "alert_mask": lt.alert.category_t.error_notification
                | lt.alert.category_t.status_notification,
    "connections_limit": 400,
    "active_downloads": 1, "active_seeds": 1,
})
for r in [("router.bittorrent.com", 6881), ("dht.transmissionbt.com", 6881),
          ("router.utorrent.com", 6881), ("dht.libtorrent.org", 25401)]:
    ses.add_dht_router(*r)

atp = lt.add_torrent_params()
if os.path.exists(RESUME):
    atp = lt.read_resume_data(open(RESUME, "rb").read())
atp.ti = lt.torrent_info(os.path.join(D, "flock.torrent"))
atp.save_path = D
atp.storage_mode = lt.storage_mode_t.storage_mode_sparse
h = ses.add_torrent(atp)
h.add_url_seed(WEB_SEED)
for t in ["udp://tracker.opentrackr.org:1337/announce",
          "udp://open.demonii.com:1337/announce",
          "udp://tracker.torrent.eu.org:451/announce",
          "udp://exodus.desync.com:6969/announce"]:
    h.add_tracker({"url": t})

def log(msg):
    with open(os.path.join(D, "bt.log"), "a") as f:
        f.write(f"{datetime.datetime.now().isoformat(timespec='seconds')} {msg}\n")

log(f"start: {atp.ti.name()} {atp.ti.total_size()/1024**3:.2f} GiB, web seed {WEB_SEED}")
last_save = 0
while True:
    s = h.status()
    with open(os.path.join(D, "heartbeat"), "w") as f:
        f.write(f"{datetime.datetime.now().isoformat(timespec='seconds')}\n"
                f"state={s.state} progress={s.progress*100:.2f}% "
                f"done={s.total_done/1024**3:.2f}/{atp.ti.total_size()/1024**3:.2f} GiB\n"
                f"down={s.download_rate/1e6:.2f} MB/s up={s.upload_rate/1e6:.2f} MB/s "
                f"peers={s.num_peers} seeds={s.num_seeds}\n")
    for a in ses.pop_alerts():
        if a.category() & lt.alert.category_t.error_notification:
            log(f"ALERT {type(a).__name__}: {a.message()}")
    if time.time() - last_save > 120:
        h.save_resume_data()
        last_save = time.time()
        for a in ses.pop_alerts():
            if isinstance(a, lt.save_resume_data_alert):
                open(RESUME, "wb").write(lt.write_resume_data_buf(a.params))
    if s.is_seeding or s.progress >= 1.0:
        log(f"COMPLETE {s.total_done/1024**3:.2f} GiB")
        with open(os.path.join(D, "DONE"), "w") as f:
            f.write(f"complete {datetime.datetime.now().isoformat()}\n")
        break
    time.sleep(5)
