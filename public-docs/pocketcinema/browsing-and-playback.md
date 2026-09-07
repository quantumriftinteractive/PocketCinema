# Browsing and playback

The home menu provides search, account-backed browsing, Live TV, Quick Resume, Continue Watching, and settings where those features have available data. Choose a title, episode, or stream and PCServer prepares the device-facing play path.

## My Library

Link a Stremio account through **Stremio Account** to use **My Library**. The
menu provides separate **Movies** and **Series** lists from that account. Long
lists are paged, with at most 60 content items shown per page.

Library state is read-only in PocketCinema. Movie and series selections do not
add, remove, or update Stremio library entries. Series screens show watched
seasons and watched or current episodes where the account provides that state.
Selecting a movie, series, season, or episode continues into the ordinary
source-selection and playback flow.

PCServer may direct-play a compatible source or convert/downscale it for the Miyoo. The device receives a server URL rather than a raw addon or upstream URL. Startup can take time while compatibility and conversion work are prepared.

In selectors, Up/Down navigate, A selects, and B goes back. During FFplay playback, the Miyoo Menu button exits; B is frame-step behavior on the target FFplay build. PocketCinema cleans up temporary playback state after exit or failure.
