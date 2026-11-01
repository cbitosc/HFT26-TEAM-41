// Engravings cut from the team's asset sheets by scripts/cut-greek.mjs (4x the sheet
// resolution). Sizes are the files' pixel sizes, used for aspect ratios.
export const GREEK = {
  athena: [1256, 1952],
  pegasus: [1488, 1360],
  sun: [672, 656],
  moon: [432, 568],
  sky: [896, 904],
  arch: [952, 1144],
  helmet: [512, 784],
  ionic: [584, 464],
  corinthian: [528, 512],
  column: [384, 808],
  ship: [1400, 680],
  amphora: [552, 704],
  bull: [640, 664],
  hermes: [928, 1040],
  wreath: [560, 528],
  "wreath-bow": [560, 560],
  scroll: [512, 696],
  compass: [536, 616],
  torch: [224, 704],
  aegis: [640, 640],
  coast: [2576, 944],
} as const;

export type GreekName = keyof typeof GREEK;

/** Greek numerals for section labels: Α΄ Β΄ Γ΄ … (Ϛ is six). */
export const NUMERALS = ["Α", "Β", "Γ", "Δ", "Ε", "Ϛ", "Ζ", "Η", "Θ", "Ι"];
