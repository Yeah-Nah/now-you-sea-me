# Recommended Edge Setup (High Level)

This project is best served by a small, self-contained edge device that can run DepthAI locally and write video files directly to storage. A Raspberry Pi 4/5 is the most practical option because it is portable, well-supported by DepthAI, and easy to power and store recordings on.

## Recommended Approach

Use a Raspberry Pi as the on-site controller for the OAK-D camera. The Pi runs a lightweight DepthAI pipeline, records video to local storage, and can later be expanded with a display or remote access if needed.

## Why This Works Well

- Portable and battery friendly
- Runs the same DepthAI workflows you already know
- Easy to save recordings to SD or SSD
- Simple to expand with a screen or controls

## Core Hardware (High Level)

- Raspberry Pi 4 or 5
- OAK-D camera (USB connection to Pi)
- MicroSD or USB SSD for storage
- External battery pack (USB-C)

## Immediate Next Steps (While Waiting For Parts)

You can start now by updating your existing DepthAI script on your current computer to record and timestamp video. This keeps your pipeline code ready to move to the Pi later.

1. Add timestamp-based filenames for each recording (for example, `YYYYMMDD_HHMMSS.mp4`).
2. Confirm the script creates the output folder if it does not exist.
3. Record short test clips to validate: 
   - file creation, 
   - codec compatibility, 
   - and playback quality.
4. Log the recording settings you plan to use (resolution, FPS, codec).
5. Keep the recording logic isolated in a function so it can be dropped into the Raspberry Pi setup unchanged.

Once the Raspberry Pi parts arrive, you will be able to run the same recording script on the Pi, point the output path to local storage, and operate fully offline.
