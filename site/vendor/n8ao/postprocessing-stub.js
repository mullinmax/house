// N8AO.js imports Pass from pmndrs "postprocessing" for its N8AOPostPass, which this site does not use (it uses
// N8AOPass with three's own EffectComposer). This empty base class stands in so that 600 KB library is not loaded.
export class Pass {}
