import { formatBytes, formatPercent, getThresholdStateColor } from '../utils/formatters'
import { StatusBadge } from './StatusBadge'

interface StorageGaugeProps {
  totalBytes: number
  availableBytes: number
  warningThreshold: number
  admissionFloor: number
  emergencyThreshold: number
  criticalThreshold: number
  currentState: string
  inodeTotal: number
  inodeAvailable: number
  inodeUsagePercent: number | null
}

export function StorageGauge({
  totalBytes,
  availableBytes,
  warningThreshold,
  admissionFloor,
  emergencyThreshold,
  criticalThreshold,
  currentState,
  inodeTotal,
  inodeAvailable,
  inodeUsagePercent,
}: StorageGaugeProps) {
  const usedBytes = totalBytes - availableBytes
  const usedPercent = (usedBytes / totalBytes) * 100
  const warningPercent = ((totalBytes - warningThreshold) / totalBytes) * 100
  const floorPercent = ((totalBytes - admissionFloor) / totalBytes) * 100
  const emergencyPercent = ((totalBytes - emergencyThreshold) / totalBytes) * 100

  const stateColor = getThresholdStateColor(currentState)

  return (
    <div className="storage-gauge" style={{ '--state-color': stateColor } as React.CSSProperties}>
      <div className="gauge-header">
        <h3 className="gauge-title">Storage Overview</h3>
        <StatusBadge variant="threshold" color={stateColor}>
          {currentState}
        </StatusBadge>
      </div>

      <div className="gauge-main">
        <svg className="gauge-svg" viewBox="0 0 200 200" role="img" aria-label={`Storage usage ${formatPercent(usedBytes, totalBytes)}`}>
          <defs>
            <linearGradient id="gauge-gradient" x1="0" y1="0" x2="1" y2="0">
              <stop offset="0%" stopColor="var(--state-normal)" />
              <stop offset={`${Math.min(warningPercent, 100)}%`} stopColor="var(--state-warning)" />
              <stop offset={`${Math.min(floorPercent, 100)}%`} stopColor="var(--state-blocked)" />
              <stop offset={`${Math.min(emergencyPercent, 100)}%`} stopColor="var(--state-emergency)" />
              <stop offset="100%" stopColor="var(--state-critical)" />
            </linearGradient>
          </defs>

          <circle
            className="gauge-bg"
            cx="100"
            cy="100"
            r="80"
            fill="none"
            stroke="var(--bg-card-border)"
            strokeWidth="16"
          />
          <circle
            className="gauge-progress"
            cx="100"
            cy="100"
            r="80"
            fill="none"
            stroke="url(#gauge-gradient)"
            strokeWidth="16"
            strokeDasharray={`${Math.min(usedPercent, 100) * 5.0265} 502.65`}
            strokeLinecap="round"
            transform="rotate(-90 100 100)"
            style={{ filter: 'drop-shadow(0 0 8px var(--state-color))' }}
          />

          <circle
            className="gauge-floor-marker"
            cx="100"
            cy="100"
            r="80"
            fill="none"
            stroke="var(--red)"
            strokeWidth="2"
            strokeDasharray="4 12"
            strokeDashoffset={-floorPercent * 5.0265}
            transform="rotate(-90 100 100)"
            opacity="0.6"
          />
        </svg>

        <div className="gauge-center">
          <div className="gauge-value">{formatBytes(availableBytes)}</div>
          <div className="gauge-label">Available</div>
          <div className="gauge-sub">of {formatBytes(totalBytes)} total</div>
        </div>
      </div>

      <div className="gauge-legend">
        <div className="legend-item">
          <span className="legend-marker" style={{ background: 'var(--state-normal)' }} />
          <span>{`Normal > ${formatBytes(warningThreshold)}`}</span>
        </div>
        <div className="legend-item">
          <span className="legend-marker" style={{ background: 'var(--state-warning)' }} />
          <span>{`Warning <= ${formatBytes(warningThreshold)}`}</span>
        </div>
        <div className="legend-item floor">
          <span className="legend-marker floor-marker" />
          <span>Admission Floor: {formatBytes(admissionFloor)}</span>
        </div>
        <div className="legend-item">
          <span className="legend-marker" style={{ background: 'var(--state-emergency)' }} />
          <span>{`Emergency <= ${formatBytes(emergencyThreshold)}`}</span>
        </div>
        <div className="legend-item">
          <span className="legend-marker" style={{ background: 'var(--state-critical)' }} />
          <span>{`Critical <= ${formatBytes(criticalThreshold)}`}</span>
        </div>
      </div>

      {inodeUsagePercent !== null && (
        <div className="gauge-inodes">
          <div className="inodes-label">
            <span>Inodes</span>
            <span>{inodeUsagePercent}% used</span>
          </div>
          <div className="inodes-bar">
            <div
              className="inodes-fill"
              style={{
                width: `${Math.min(inodeUsagePercent, 100)}%`,
                background: inodeUsagePercent > 90 ? 'var(--red)' : inodeUsagePercent > 75 ? 'var(--gold)' : 'var(--cyan)',
              }}
            />
          </div>
          <div className="inodes-detail">
            {formatBytes(inodeAvailable)} available of {formatBytes(inodeTotal)}
          </div>
        </div>
      )}
    </div>
  )
}