# Supplemental demo samples

- `real-world/`: five Internet-sourced images shown in Live Inference under **Real-world samples**. `manifest.json` owns their SHA-256 checksums, source/author/license links, two Vietnamese question styles, and authored expected answers. Images remain local and are served through the API asset allowlist.
- `dataset-comparison/`: five PlantVillage images provided alongside the Internet examples, retained for manual comparison. These are not added to the web gallery; the existing report-backed PlantVillage gallery stays unchanged.
- `demo_questions.md`: the supplied Vietnamese question sheet for all ten images, with original dataset identifiers and source descriptions. Its disease descriptions and expected answers are demo annotations, not independently verified diagnoses.

The real-world group has ten questions: one dataset-style question and one natural question per image. Expected answers are hidden from the public sample list, sent only as started-job metadata, and never included in model prompts or exact-match scoring. Editing a question clears its expected answer. These examples do not change report snapshots, splits, or benchmark metrics.

## Image attribution

The supplied files are resized Wikimedia Commons downloads; this integration does not edit the image bytes. Each file retains its own license, independent of the application code. Source descriptions supply the provisional crop/disease associations. “Real-world” identifies external examples, not a claim that every photograph has a natural field background: the grape photograph shows a specimen on a plain surface.

| File | Author | Source | License |
| --- | --- | --- | --- |
| `real-world/rw01_tomato_early_blight.jpg` | Dwight Sipler | [Early blight on tomato leaves](https://commons.wikimedia.org/wiki/File:Early_blight_on_tomato_leaves_(7871930010).jpg) | [CC BY 2.0](https://creativecommons.org/licenses/by/2.0/) |
| `real-world/rw02_tomato_late_blight.jpg` | Scot Nelson | [Tomato late blight leaf](https://commons.wikimedia.org/wiki/File:Tomato_late_blight_leaf_sporulating_lesions_1_(5816170621).jpg) | [CC0 1.0](https://creativecommons.org/publicdomain/zero/1.0/) |
| `real-world/rw03_apple_scab.jpg` | James Lindsey at Ecology of Commanster | [Venturia inaequalis](https://commons.wikimedia.org/wiki/File:Venturia.inaequalis2.-.lindsey.jpg) | [CC BY-SA 3.0](https://creativecommons.org/licenses/by-sa/3.0/) |
| `real-world/rw04_grape_black_rot.jpg` | Mary Ann Hansen, Virginia Tech, Bugwood.org | [Black rot on grape](https://commons.wikimedia.org/wiki/File:Guignardia_bidwellii_(black_rot)_on_grape_4.jpg) | [CC BY 3.0 US](https://creativecommons.org/licenses/by/3.0/us/) |
| `real-world/rw05_corn_common_rust.jpg` | Daren Mueller, Iowa State University, Bugwood.org | [Puccinia sorghi](https://commons.wikimedia.org/wiki/File:Puccinia_sorghi_(09).jpg) | [CC BY 3.0 US](https://creativecommons.org/licenses/by/3.0/us/) |

To add another example, place its image in `real-world/` and add an entry to the manifest with a unique image/question ID, checksum, attribution, license and Vietnamese questions. Use `expected_answer` for authored notes; do not add a dataset `reference` for external images. Restart the backend after changing the manifest.
