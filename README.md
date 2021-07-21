# Syncify

The package that puts your local playlists online.

This main purpose of this package is to sync your local m3u playlists with playlists on Spotify. It does so by searching for your songs on Spotify via their tags, associating a Spotify URI with each, and building playlists from these URIs based upon the songs found in your local m3u playlists.

Supports cross platform for all features apart from data folder storage. If you intend to use this package across multiple platforms, it is advised to use the default data folder path in the packages root directory. This can be most easily achieved by not defining a data path.

I developed this program for my own use so I can share my local playlists with friends online. In the process however, the program branched out to a package that now helps me manage other aspects of my library through Spotify including tagging and embedded images. I am planning on implementing more features in the future, but if there's something you would like to see added please do let me know! I'm hoping to make it as general-use as possible, so any ideas or contributions you have will be greatly appreciated!

The package is completely open-source and reproducible. Use as you like, but be sure to credit your sources! More information on each function can be found in the [documentation](https://github.com/jor-mar/syncify/blob/master/DOCUMENTATION.md).

## First time run

Clone this repo to your Python package directory and run ```pip install .``` from the command line while in the package root directory.

The program is intended for use from the command line. To run the program in this way, you will need to set the environment variables. This can be most easily achieved in a Python CLI, Jupyter Notebook, or manually by saving the variables to a '.env' file in the package root directory.

### Get Spotify Developer access

You will need first need to get access to the [Spotify API](https://developer.spotify.com/dashboard/login). Create an app and take note of the Client ID and Client Secret. You'll need to use these in the next steps.

### Through Python CLI or Jupyter Notebook

Upon instantiation of the main Syncify object, you may define the necessary variables as parameters. To persist these parameter variables to storage, you can run the 'set_env()' method on the base object. The parameters are as follows:

> - base_api: Base link to access Spotify API.
> - base_auth: Base link to authorise through Spotify API.
> - open_url: Base link for user facing links to Spotify items.
> - c_id: ID of developer API access.
> - c_secret: Secret code for developer API access.
> > 
> - playlists: Relative path to folder containing .m3u playlists. Must be a folder in the music folder path.
> - win_path: Windows specific path to all music files. (Optional: only 1 path needed)
> - mac_path: Mac specific path to all music files. (Optional: only 1 path needed)
> - lin_path: Linux specific path to all music files. (Optional: only 1 path needed)
> >
> - data: Path to folder containing json and image files. (Optional: will store to 'data' folder in root of package if not defined)
> - uri_file: Filename of URI json file without extension.
> - token_file: Filename of Spotify access token json file without extension.

Run the following code to import and instantiate the main Syncify object with the necessary variables as keyword arguments (\*\*kwargs).

```py
from syncify.Syncify import Syncify
main = Syncify(**kwargs, verbose=True, auth=False)
main.set_env()
```

> NOTE: If you intend to use this package across multiple platforms, it is advised to use the default data folder path in the packages root directory. This can be most easily achieved by not defining a data path.

Alternatively, you may also set environment variables separate to those of the current object by setting them as parameters of the set_env() method. In this case, the environment variable names of the kwargs must be given as they are listed in the manual list below.

```py
from syncify.Syncify import Syncify
main = Syncify(verbose=True, auth=False)
main.set_env(current_state=False, **kwargs)
```

### Manually create .env

Create a file named '.env' in the package root directory with the following variables.

> - BASE_API: 		Base link to access Spotify API.
> - BASE_AUTH:		Base link to authorise through Spotify API.
> - OPEN_URL:		Base link for user facing links to Spotify items.
> - CLIENT_ID:		ID of developer API access.
> - CLIENT_SECRET:	Secret code for developer API access. 
> - PLAYLISTS:		Relative path to folder containing .m3u playlists, must be in music folder.
> - WIN_PATH:		Windows specific path to all music files.
> - MAC_PATH:		Mac specific path to all music files.
> - LIN_PATH:		Linux specific path to all music files.
> - DATA_PATH:		Path to folder containing json and image files.
> - URI_FILENAME:	Filename of URI json file.
> - TOKEN:			Filename of Spotify access token json file.

#### Example

> BASE_API=https://api.spotify.com/v1<br>
> BASE_AUTH=https://accounts.spotify.com<br>
> OPEN_URL=https://open.spotify.com<br>
> CLIENT_ID=1234<br>
> CLIENT_SECRET=1234<br>
> PLAYLISTS=Playlists<br>
> WIN_PATH=D:\Music<br>
> LIN_PATH=/media/user/music<br>
> MAC_PATH=/media/music<br>
> DATA_PATH=D:\Data<br>
> URI_FILENAME=URIs<br>
> TOKEN=token<br>

### User Authorisation

You will also need to authorise this app with your personal user profile on Spotify to enable it to make changes to your playlists. By default, the app has access to read and write to your public and private playlists, and read your collaborative playlists. Run the function below, it will open your browser so that you can authorise it. It will redirect you to a new web page that will give you an error. This is fine, just copy the link to the input box provided. Your token will now be saved to your data folder where it will automatically refresh everytime you run the app.

```py
from syncify.Syncify import Syncify
main = Syncify(verbose=True, auth=False)
main.auth()
```

## Usage

The following commands cover the main functions of the package through the command line. However, many methods go into making these functions work, through which a custom usage can be achieved. More information on these can be found in the [documentation](https://github.com/jor-mar/syncify/blob/master/DOCUMENTATION.md).

Each function is listed as a make function (if installed) and Python command. You need only use one. Ensure you are in the root directory of the package when running these functions.

### Update Spotify playlists

```sh
make update_playlists
python main.py update
```

This function automatically loads your Spotify and local m3u playlists from the defined playlists folder. It will import URIs from the URIs json file defined in instantiation or environment, updating locally stored URIs with matches from your Spotify playlists. This is useful in the case where searching finds the wrong song in the first pass, you can manually replace this song in the playlist with this part of the function automatically updating the associated URI.

It then searches for any songs that are not listed in the URIs json file. If a song is listed but has a null value, it will not search or add this song. This is to avoid attempting to search for songs which do not exist on Spotify.

Once it has searched for missing songs, it will compare the new songs' associated URIs for each playlist to your Spotify playlists and add any not already listed. Lastly, it will rescan your Spotify playlists and produce a difference report showing you which Spotify playlists have extra or missing songs.

**Refresh Spotify playlists** - Performs the same function as the update, but clears out all songs from your linked Spotify playlists first, re-adding all locally associated URIs.

```sh
make refresh_playlists
python main.py refresh
```

*These functions produce/update the following files in the data folder:*

- **m3u_metadata.json**: Metadata of every song in each m3u playlist.
- **search_found.json**: All songs found during the search phase.
- **search_not_found.json**: All songs not found during the search phase.
- **search_added.json**: All songs added to each playlist.
- **<URI_FILENAME>.json**: Creates/updates associated URIs in this json.
- **<URI_FILENAME>_updated.json**: List of songs that have had their associated URIs modified by manual user replacement.
- **spotify_extra.json**: Extra URIs in Spotify playlists not found in local playlists.
- **spotify_missing.json**: Songs found in local playlists that do not have an associated URI to add to Spotify.

### Report on differences between local and Spotify playlists

```sh
make generate_report
python main.py differences
```

Compares associated URIs for m3u playlists with Spotify playlists to produce a difference report showing you which Spotify playlists have extra or missing songs.

*This function produces the following files in the data folder:*

- **spotify_extra.json**: Extra URIs in Spotify playlists not found in local playlists.
- **spotify_missing.json**: Songs found in local playlists that do not have an associated URI to add to Spotify.

### Update embedded artwork for local files

```sh
make add_artwork
python main.py artwork
```

Embeds the largest image from Spotify for each associated URI to each song in your local library.

**Report which files have missing embedded artwork** - Produce a report on which songs in your local library do not have embedded images.

```sh
make no_images
python main.py no_images
```

*This function produces the following files in the data folder:*

- **no_images.json**: Songs with no embedded image by album.
- **m3u_metadata.json**: Metadata of every song in each m3u playlist.

### Extract images

**Local library:**
```sh
make extract_local_images
python main.py extract_local
```

**Spotify playlists:**
```sh
make extract_spotify_images
python main.py extract_spotify
```

Saves embedded images for your entire library or Spotify playlists to your local storage as jpg or png. Files are stored in your data folder as images/local/\<albums\> or images/Spotify/\<playlists\>

*These functions produce/update the following files in the data folder:*

- **m3u_metadata.json**: Metadata of every song in each m3u playlist.

### Get URIs for entire library and check on Spotify

```sh
make check_uri
python main.py check
```

This function loads your entire library, searching for any song that is not listed in the associated URIs json file, skipping any listed with null value. It then creates Spotify for all the songs it has found per album, allowing you to check the URIs it has found, and replace incorrectly associated URIs manually in the json file that opens automatically.

**Only check currently associated URIs** - This does the same as above, skipping any searches, and simply creating playlists out of already associated URIs per album.

```sh
make check_uri_simple
python main.py simplecheck
```

*These functions produce/update the following files in the data folder:*

- **m3u_metadata.json**: Metadata of every song in each m3u playlist.
- **search_found.json**: All songs found during the search phase.
- **search_not_found.json**: All songs not found during the search phase.
- **search_added.json**: All songs added to each playlist.
- **<URI_FILENAME>.json**: Creates/updates associated URIs in this json.

## Contributions/reporting issues

This package was originally intended for personal use in order to solve some issues I've faced managing a local music library. However, I would like to make this package as accessible to others as possible. If you have any suggestions, wish to contribute, or have any issues to report, please do let me know via the issues tab or make a new pull request with your new feature for review. Otherwise, I hope you enjoy using Syncify!
