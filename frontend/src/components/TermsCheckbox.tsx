import clsx from 'clsx'
import { forwardRef, type InputHTMLAttributes } from 'react'

type TermsCheckboxProps = Omit<InputHTMLAttributes<HTMLInputElement>, 'type'> & { error?: string }

/** Acceptation des CGU/CGV et de la politique de confidentialité (inscription, invitation).
 * Les textes s'ouvrent dans un nouvel onglet pour ne pas perdre le formulaire. */
export const TermsCheckbox = forwardRef<HTMLInputElement, TermsCheckboxProps>(function TermsCheckbox(
  { id, error, className, ...props },
  ref,
) {
  return (
    <div className={className}>
      <label htmlFor={id} className="flex cursor-pointer items-start gap-3 text-[13px] leading-relaxed text-slate-600">
        <input
          ref={ref}
          id={id}
          type="checkbox"
          aria-invalid={Boolean(error)}
          className={clsx(
            'mt-0.5 h-[18px] w-[18px] shrink-0 cursor-pointer rounded border-slate-300 accent-brand-600',
            error && 'outline outline-2 outline-red-300',
          )}
          {...props}
        />
        <span>
          J’accepte les{' '}
          <a href="/cgu" target="_blank" rel="noopener" className="font-semibold text-brand-600 hover:text-brand-700">
            conditions générales d’utilisation et de vente
          </a>{' '}
          et la{' '}
          <a
            href="/confidentialite"
            target="_blank"
            rel="noopener"
            className="font-semibold text-brand-600 hover:text-brand-700"
          >
            politique de confidentialité
          </a>
          .
        </span>
      </label>
      {error && <p className="field-error">{error}</p>}
    </div>
  )
})
