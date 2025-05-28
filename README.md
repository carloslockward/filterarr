# filterarr

filterarr is a small Python tool to automate filtering and blacklisting of torrents with unwanted file extensions in your media automation pipeline.

It works with [qBittorrent](https://www.qbittorrent.org/), [Sonarr](https://sonarr.tv/), and [Radarr](https://radarr.video/). If a torrent in qBittorrent contains files with blacklisted extensions (e.g. `.rar`, `.r00`, `.zip`, `.lnk`), filterarr removes the torrent and blacklists the release in Sonarr or Radarr so it won’t be downloaded again.

## Features

- Scans all torrents in qBittorrent for forbidden file extensions
- Supports wildcards to match extensions (`.r*`, `.zip*`, etc)
- Removes matching torrents safely
- Blacklists the corresponding release in Sonarr or Radarr by marking it as failed

## Why?

Many unwanted or unsafe torrents, such as those containing `.rar` archives or dangerous Windows shortcut files (`.lnk`) can be picked up automatically by Sonarr or Radarr. These files can disrupt your media automation, causing missing or unimported episodes and movies, and may even pose security risks. filterarr helps keep your library safer and your automation cleaner by blocking such torrents at download time.

## License

[Creative Commons Attribution-NonCommercial 4.0 International (CC BY-NC 4.0)](https://creativecommons.org/licenses/by-nc/4.0/)

## Credits

filterarr by @carloslockward

Uses:

- [requests](https://docs.python-requests.org/)
- Sonarr, Radarr, qBittorrent APIs

---

#### Contributions and bug reports welcome!
