import React from 'react'

interface FormFieldProps {
  id: string
  label: string
  value: number | string
  onChange: (val: number | string) => void
  type?: 'number' | 'text' | 'datetime-local'
  step?: number | string
  min?: number | string
  max?: number | string
  unit?: string
  helpText?: string
  error?: string
  disabled?: boolean
  required?: boolean
}

export const FormField: React.FC<FormFieldProps> = ({
  id,
  label,
  value,
  onChange,
  type = 'number',
  step = 'any',
  min,
  max,
  unit,
  helpText,
  error,
  disabled = false,
  required = false,
}) => {
  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const raw = e.target.value
    if (type === 'number') {
      const parsed = parseFloat(raw)
      onChange(isNaN(parsed) ? raw : parsed)
    } else {
      onChange(raw)
    }
  }

  const hasError = Boolean(error)

  return (
    <div className="flex flex-col space-y-1">
      <div className="flex items-center justify-between">
        <label
          htmlFor={id}
          className="text-xs font-medium text-slate-300 flex items-center gap-1"
        >
          {label}
          {required && <span className="text-rose-400">*</span>}
        </label>
        {unit && (
          <span className="text-[11px] font-mono text-slate-400 bg-slate-800/80 px-1.5 py-0.5 rounded border border-slate-700/60">
            {unit}
          </span>
        )}
      </div>

      <div className="relative">
        <input
          id={id}
          name={id}
          type={type}
          value={value}
          step={step}
          min={min}
          max={max}
          disabled={disabled}
          onChange={handleChange}
          aria-invalid={hasError}
          aria-describedby={hasError ? `${id}-error` : helpText ? `${id}-help` : undefined}
          className={`w-full px-2.5 py-1.5 text-sm bg-slate-900 border rounded-md font-mono text-slate-100 placeholder-slate-500 focus:outline-none focus:ring-1 transition-colors ${
            hasError
              ? 'border-rose-500/80 focus:border-rose-500 focus:ring-rose-500/30'
              : 'border-slate-700 focus:border-indigo-500 focus:ring-indigo-500/30'
          } ${disabled ? 'opacity-50 cursor-not-allowed' : ''}`}
        />
      </div>

      {hasError ? (
        <p id={`${id}-error`} className="text-[11px] text-rose-400 mt-0.5" role="alert">
          {error}
        </p>
      ) : helpText ? (
        <p id={`${id}-help`} className="text-[11px] text-slate-400 mt-0.5">
          {helpText}
        </p>
      ) : null}
    </div>
  )
}
