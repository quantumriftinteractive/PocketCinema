# Live TV

Live TV is account-backed. PCServer discovers compatible `type=tv` catalogs from the linked Stremio account and presents their channels through PocketCinema. The list depends on the addons installed on that account; PocketCinema does not ship a built-in country or channel catalog and does not filter channels by addon name or country.

Select a channel to request its stream. PCServer keeps the upstream URL private and either serves a compatible path or performs the supported bounded HLS conversion for the Miyoo. Live streams may take longer to start and may have limited seeking compared with on-demand media.
