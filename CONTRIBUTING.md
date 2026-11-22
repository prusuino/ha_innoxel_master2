# Contributing

Bug reports, ideas and pull requests are welcome — especially reports from installations with dimmers, blinds or a weather station, which could not be tested on the bench.

## Reporting a problem

Open an issue with the *Bug report* form. The version of the integration, the Home Assistant version and the firmware revision of the master (shown on the device page) answer most first questions.

## Pull requests

- Keep a pull request to one topic; a small one is reviewed faster.
- Code, comments and commit messages are in English.
- Texts shown in the interface live in `custom_components/innoxel_master2/strings.json` and in `translations/` (de, en, fr, it). A new text needs an entry in each of them.
- Run the tests before you push. They talk to a stand-in master on localhost, no hardware is needed:

  ```
  pip install pytest pytest-homeassistant-custom-component
  pytest tests
  ```

- Add a line to `CHANGELOG.md` under the next version.
- Do not commit addresses of real installations.

## Licence

Contributions are published under the licence of this repository, see `LICENSE`.
