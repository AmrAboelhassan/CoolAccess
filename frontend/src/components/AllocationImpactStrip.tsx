import React from 'react';
import { ArrowRight, Cpu, Scale, Thermometer, Users } from 'lucide-react';
import { AllocationResponse, Facility, ScenarioResponse } from '../types';

interface AllocationImpactStripProps {
  allocation: AllocationResponse | null;
  facilities: Facility[];
  currentTimestamp: string;
  onSelectTimestamp: (timestamp: string) => void;
  primaryTransition?: ScenarioResponse['primary_transition'];
}

function formatNumber(value: number, fractionDigits: number = 2): string {
  return value.toLocaleString(undefined, {
    minimumFractionDigits: fractionDigits,
    maximumFractionDigits: fractionDigits,
  });
}

export const AllocationImpactStrip: React.FC<AllocationImpactStripProps> = ({
  allocation,
  facilities,
  currentTimestamp,
  onSelectTimestamp,
  primaryTransition,
}) => {
  if (!allocation) {
    return (
      <section className="allocation-impact-strip allocation-impact-loading" aria-live="polite">
        Loading authoritative decision proof for {currentTimestamp} UTC…
      </section>
    );
  }

  const facilityById = Object.fromEntries(
    facilities.map((facility) => [facility.facility_id, facility])
  );
  const staticIds = allocation.static_baseline.selected_facility_ids;
  const dynamicIds = allocation.selected_facility_ids;
  const removedIds = staticIds.filter((facilityId) => !dynamicIds.includes(facilityId));
  const addedIds = dynamicIds.filter((facilityId) => !staticIds.includes(facilityId));
  const hasSetChange = removedIds.length > 0 || addedIds.length > 0;
  const staticGain = allocation.static_baseline.absolute_gain;
  const staticGainPct = allocation.static_baseline.percentage_gain;
  const populationDelta =
    allocation.coverage_metrics.covered_population - allocation.static_baseline.covered_population;
  const naiveGain = allocation.naive_baseline.absolute_gain;
  const transitionTimestamp = primaryTransition?.future_timestamp_utc;
  const populationOnlySet = staticIds.join(', ');
  const thermalWeightedSet = dynamicIds.join(', ');
  const isPrimaryTransition =
    hasSetChange && transitionTimestamp !== undefined && allocation.timestamp === transitionTimestamp;
  const isPostTransitionRetention =
    hasSetChange && transitionTimestamp !== undefined && allocation.timestamp > transitionTimestamp;

  const facilityLabel = (facilityId: string): string => {
    const facility = facilityById[facilityId];
    return facility ? `${facility.name} (${facilityId})` : facilityId;
  };

  const allocationValue = hasSetChange
    ? `${removedIds.join(', ')} → ${addedIds.join(', ')}`
    : dynamicIds.join(' · ');
  const allocationSub = hasSetChange
    ? `${removedIds.map(facilityLabel).join(', ')} replaced by ${addedIds
        .map(facilityLabel)
        .join(', ')}`
    : `Authoritative K=${allocation.k} set is unchanged from the ${allocation.baseline_timestamp} reference.`;

  const impactNarrative = isPrimaryTransition
    ? `At ${allocation.timestamp} UTC, the population-only ablation retains {${populationOnlySet}}, while FortyGuard-weighted exact allocation selects {${thermalWeightedSet}}. Under the same K=${allocation.k} constraint, the swap does not occur without thermal weighting.`
    : isPostTransitionRetention
    ? `At ${allocation.timestamp} UTC, the deterministic optimizer retains the post-transition facility set. It remains different from the ${allocation.baseline_timestamp} reference; this is not a claim that the allocation changed again at this timestamp.`
    : hasSetChange
    ? `At ${allocation.timestamp} UTC, the authoritative facility set differs from the ${allocation.baseline_timestamp} reference under the same K=${allocation.k} constraint.`
    : currentTimestamp === allocation.baseline_timestamp
    ? `This prepared snapshot establishes the reference set. At ${transitionTimestamp ?? '20:00'}, inspect the exact facility swap, +23.68% versus static, the naive tie, and the 3,519-resident trade-off.`
    : `The prepared temperature snapshot was re-evaluated, while the authoritative K=${allocation.k} facility set remained unchanged from the reference.`;

  const handlePrimaryAction = () => {
    if (transitionTimestamp && currentTimestamp !== transitionTimestamp) {
      onSelectTimestamp(transitionTimestamp);
      return;
    }
    const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    document.querySelector('.heat-intelligence-module')?.scrollIntoView({
      behavior: reduceMotion ? 'auto' : 'smooth',
      block: 'start',
    });
  };

  return (
    <section
      className={`allocation-impact-strip ${hasSetChange ? 'allocation-impact-changed' : ''}`}
      aria-labelledby="allocation-impact-heading"
    >
      <div className="allocation-impact-header">
        <div>
          <span className="allocation-impact-kicker">Decision proof</span>
          <h2 id="allocation-impact-heading" className="allocation-impact-title">
            {isPrimaryTransition
              ? `FortyGuard weighting changes the ${allocation.timestamp} K=${allocation.k} optimum`
              : hasSetChange
              ? `The K=${allocation.k} allocation differs from the ${allocation.baseline_timestamp} reference`
              : currentTimestamp === allocation.baseline_timestamp && transitionTimestamp
              ? `K=${allocation.k} of ${facilities.length}: inspect the ${transitionTimestamp} facility swap`
              : 'Reference allocation for the temperature-driven comparison'}
          </h2>
          <p className="allocation-impact-narrative">{impactNarrative}</p>
        </div>
        <button type="button" className="allocation-impact-action" onClick={handlePrimaryAction}>
          <span>
            {currentTimestamp === transitionTimestamp
              ? 'Ask why this changed'
              : transitionTimestamp
              ? `Show ${transitionTimestamp} change`
              : 'Ask about this allocation'}
          </span>
          <ArrowRight size={14} />
        </button>
      </div>

      <div className="allocation-impact-grid">
        <article className="allocation-impact-cell">
          <div className="allocation-impact-label">
            <Cpu size={13} /> Allocation set
          </div>
          <strong className="allocation-impact-value font-mono">{allocationValue}</strong>
          <span className="allocation-impact-sub">{allocationSub}</span>
        </article>

        <article className="allocation-impact-cell allocation-impact-primary">
          <div className="allocation-impact-label">
            <Thermometer size={13} /> Heat-weighted demand vs static
          </div>
          <strong className="allocation-impact-value font-mono">
            {staticGain > 0.005
              ? `+${formatNumber(staticGain)} · +${staticGainPct.toFixed(2)}%`
              : staticGain < -0.005
              ? `${formatNumber(Math.abs(staticGain))} lower`
              : 'Same objective'}
          </strong>
          <span className="allocation-impact-sub">
            Dynamic objective: {formatNumber(allocation.coverage_metrics.covered_heat_weighted_demand)}
          </span>
        </article>

        <article className="allocation-impact-cell">
          <div className="allocation-impact-label">
            <Users size={13} /> Population trade-off
          </div>
          <strong className="allocation-impact-value font-mono">
            {populationDelta > 0
              ? `+${populationDelta.toLocaleString()} residents`
              : populationDelta < 0
              ? `${Math.abs(populationDelta).toLocaleString()} fewer residents`
              : 'Same resident coverage'}
          </strong>
          <span className="allocation-impact-sub">
            {allocation.coverage_metrics.covered_population.toLocaleString()} residents covered
          </span>
        </article>

        <article className="allocation-impact-cell">
          <div className="allocation-impact-label">
            <Scale size={13} /> Naive hottest-catchment baseline
          </div>
          <strong className="allocation-impact-value font-mono">
            {Math.abs(naiveGain) <= 0.005
              ? 'Tie · 0.00 gain'
              : naiveGain > 0
              ? `+${formatNumber(naiveGain)} vs naive`
              : `${formatNumber(Math.abs(naiveGain))} below naive`}
          </strong>
          <span className="allocation-impact-sub">
            {Math.abs(naiveGain) <= 0.005
              ? 'Same facility set and objective at this timestamp.'
              : 'Compared under the same facility-count constraint.'}
          </span>
        </article>
      </div>
    </section>
  );
};
