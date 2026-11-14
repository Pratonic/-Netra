export const POLICY = Object.freeze({ deadline: 2000, match: .48, unknown: .64, margin: .08, minSamples: 2 });
export function nearest(descriptor, users) {
  return users.map(user => ({ user, distance: Math.min(...user.descriptors.map(d => Math.hypot(...d.map((v,i) => v-descriptor[i])))) })).sort((a,b) => a.distance-b.distance);
}
export function decide(e) {
  const review = reason => ({ outcome: 'review', reason });
  if (e.elapsed > POLICY.deadline) return review('Decision deadline exceeded. Retry with better lighting.');
  if (e.multiple) return { outcome: 'deny', reason: 'Multiple people detected. Only one person may enter.' };
  if (!e.samples || e.samples < POLICY.minSamples) return review('Insufficient usable frames. Face the camera and retry.');
  if (!e.quality) return review('Image quality is too low. Improve lighting and move closer.');
  if (!e.consistent) return review('Identity changed between frames. Retry alone.');
  if (!Number.isFinite(e.distance)) return review('No enrolled identity is available.');
  if (e.distance > POLICY.unknown) return { outcome: 'deny', reason: 'Face does not match an enrolled person.' };
  if (e.distance > POLICY.match || e.margin < POLICY.margin) return review('Identity match is ambiguous. Ask an administrator to verify.');
  if (!e.active) return { outcome: 'deny', reason: 'This identity has been suspended.' };
  if (!e.liveness) return review('Liveness prompt was not completed. Retry or request an attendant.');
  return { outcome: 'allow', reason: 'Enrolled identity matched and active liveness prompt passed.' };
}
export function metrics(events) {
  const measured = events.filter(e => !e.demo);
  const attacks = measured.filter(e => ['print','screen','video','mask'].includes(e.groundTruth));
  const genuine = measured.filter(e => e.groundTruth === 'genuine');
  return {
    count: measured.length,
    mean: measured.length ? measured.reduce((n,e)=>n+e.elapsed,0)/measured.length : null,
    p95: measured.length ? measured.map(e=>e.elapsed).sort((a,b)=>a-b)[Math.ceil(measured.length*.95)-1] : null,
    within: measured.length ? measured.filter(e=>e.elapsed<=POLICY.deadline).length/measured.length : null,
    apcer: attacks.length ? attacks.filter(e=>e.outcome==='allow').length/attacks.length : null,
    frr: genuine.length ? genuine.filter(e=>e.outcome!=='allow').length/genuine.length : null,
    attacks: attacks.length, genuine: genuine.length,
    review: measured.length ? measured.filter(e=>e.outcome==='review').length/measured.length : null
  };
}
