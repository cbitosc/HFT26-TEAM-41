// Engravings cut from the team's asset sheets by scripts/cut-greek.mjs (2x the sheet
// resolution). <name>.webp is the porcelain cut-out, <name>-ink.webp the line work alone
// (a CSS mask). Sizes are the files' pixel sizes: never show one larger than this.
export const GREEK = {
  "aegis": [320, 320],
  "amphora": [276, 352],
  "apollo": [428, 544],
  "arch": [476, 572],
  "athena": [672, 1000],
  "atlas": [496, 716],
  "bull": [320, 332],
  "coast": [1288, 472],
  "column": [192, 404],
  "compass": [268, 308],
  "corinthian": [264, 256],
  "helmet": [264, 380],
  "hermes-fly": [468, 644],
  "hermes": [476, 540],
  "ionic": [292, 232],
  "lion": [392, 252],
  "moon": [216, 284],
  "parthenon": [452, 380],
  "pegasus": [744, 680],
  "poseidon": [504, 584],
  "ruins": [524, 556],
  "scroll": [256, 348],
  "ship": [540, 320],
  "sky": [448, 452],
  "sun": [428, 424],
  "torch": [112, 352],
  "wreath-bow": [280, 280],
  "wreath": [280, 264],
} as const;

export type GreekName = keyof typeof GREEK;
