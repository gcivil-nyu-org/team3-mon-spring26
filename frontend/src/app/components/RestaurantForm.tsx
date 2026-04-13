import { useEffect, useState } from 'react';
import { apiFetch } from '../api';
import { Footer } from './Footer';

type Choice = { value: string; label: string };

type RestaurantPayload = {
  name: string;
  description: string;
  cuisine_type: string;
  price_range: string;
  hours_open: string;
  hours_close: string;
  address: string;
  phone: string;
  website: string;
  email: string;
};

const emptyForm: RestaurantPayload = {
  name: '',
  description: '',
  cuisine_type: 'other',
  price_range: '$$',
  hours_open: '09:00',
  hours_close: '21:00',
  address: '',
  phone: '',
  website: '',
  email: '',
};

export function RestaurantForm({ onBack }: { onBack: () => void }) {
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [hasRestaurant, setHasRestaurant] = useState(false);
  const [cuisineChoices, setCuisineChoices] = useState<Choice[]>([]);
  const [priceChoices, setPriceChoices] = useState<Choice[]>([]);
  const [form, setForm] = useState<RestaurantPayload>(emptyForm);
  const [errors, setErrors] = useState<Record<string, string[]> | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      setLoading(true);
      setLoadError(null);
      try {
        const r = await apiFetch('/api/restaurant/profile/');
        if (!r.ok) {
          if (!cancelled) setLoadError('Could not load profile.');
          return;
        }
        const d = await r.json();
        if (cancelled) return;
        setCuisineChoices(Array.isArray(d.cuisine_choices) ? d.cuisine_choices : []);
        setPriceChoices(Array.isArray(d.price_choices) ? d.price_choices : []);
        setHasRestaurant(Boolean(d.has_restaurant));
        if (d.has_restaurant && d.restaurant) {
          const rr = d.restaurant;
          setForm({
            name: rr.name ?? '',
            description: rr.description ?? '',
            cuisine_type: rr.cuisine_type ?? 'other',
            price_range: rr.price_range ?? '$$',
            hours_open: rr.hours_open || '09:00',
            hours_close: rr.hours_close || '21:00',
            address: rr.address ?? '',
            phone: rr.phone ?? '',
            website: rr.website ?? '',
            email: rr.email ?? '',
          });
        } else {
          setForm(emptyForm);
        }
      } catch {
        if (!cancelled) setLoadError('Network error.');
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const update = <K extends keyof RestaurantPayload>(key: K, value: RestaurantPayload[K]) => {
    setForm((f) => ({ ...f, [key]: value }));
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true);
    setErrors(null);
    try {
      const r = await apiFetch('/api/restaurant/profile/', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(form),
      });
      const d = await r.json().catch(() => ({}));
      if (!r.ok) {
        setErrors(d.errors && typeof d.errors === 'object' ? d.errors : { __all__: ['Could not save.'] });
        setSaving(false);
        return;
      }
      if (d.restaurant) {
        setHasRestaurant(true);
      }
      onBack();
    } catch {
      setErrors({ __all__: ['Network error.'] });
    } finally {
      setSaving(false);
    }
  };

  const title = hasRestaurant ? 'Edit restaurant profile' : 'Create restaurant profile';

  return (
    <div className="size-full flex flex-col overflow-y-auto" style={{ backgroundColor: '#FFF9F5' }}>
      <nav className="w-full px-8 py-4 flex items-center gap-4 shrink-0">
        <button
          type="button"
          onClick={onBack}
          className="text-xl p-2 rounded-lg"
          title="Back"
          style={{ border: 'none', background: 'transparent', color: '#E06E7F', cursor: 'pointer' }}
        >
          ←
        </button>
        <h1 className="text-2xl" style={{ fontFamily: 'Montserrat, sans-serif', color: '#E06E7F' }}>
          nomz
        </h1>
      </nav>

      <main className="flex-1 px-8 py-6 max-w-2xl mx-auto w-full pb-16">
        <h2 className="text-2xl mb-2" style={{ fontFamily: 'Montserrat, sans-serif', color: '#333' }}>
          {title}
        </h2>
        <p className="text-sm mb-8" style={{ fontFamily: 'Montserrat, sans-serif', color: '#666' }}>
          Matches the Django restaurant profile form. Edits re-submit your business for approval when you already have a listing.
        </p>

        {loadError && (
          <p className="text-sm mb-4" style={{ color: '#b91c1c', fontFamily: 'Montserrat, sans-serif' }}>
            {loadError}
          </p>
        )}

        {loading ? (
          <p className="text-sm" style={{ color: '#666', fontFamily: 'Montserrat, sans-serif' }}>
            Loading…
          </p>
        ) : (
          <form onSubmit={handleSubmit} className="space-y-5">
            <div>
              <label className="text-xs block mb-1" style={{ fontFamily: 'Montserrat, sans-serif', color: '#666' }}>
                Restaurant name
              </label>
              <input
                required
                value={form.name}
                onChange={(e) => update('name', e.target.value)}
                className="w-full px-4 py-2.5 border-2 rounded-lg text-sm"
                style={{ borderColor: 'rgba(224, 110, 127, 0.25)', fontFamily: 'Montserrat, sans-serif' }}
              />
            </div>
            <div>
              <label className="text-xs block mb-1" style={{ fontFamily: 'Montserrat, sans-serif', color: '#666' }}>
                Description
              </label>
              <textarea
                value={form.description}
                onChange={(e) => update('description', e.target.value)}
                rows={4}
                className="w-full px-4 py-2.5 border-2 rounded-lg text-sm resize-y min-h-[100px]"
                style={{ borderColor: 'rgba(224, 110, 127, 0.25)', fontFamily: 'Montserrat, sans-serif' }}
              />
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label className="text-xs block mb-1" style={{ fontFamily: 'Montserrat, sans-serif', color: '#666' }}>
                  Cuisine type
                </label>
                <select
                  value={form.cuisine_type}
                  onChange={(e) => update('cuisine_type', e.target.value)}
                  className="w-full px-4 py-2.5 border-2 rounded-lg text-sm"
                  style={{ borderColor: 'rgba(224, 110, 127, 0.25)', fontFamily: 'Montserrat, sans-serif' }}
                >
                  {cuisineChoices.map((c) => (
                    <option key={c.value} value={c.value}>
                      {c.label}
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label className="text-xs block mb-1" style={{ fontFamily: 'Montserrat, sans-serif', color: '#666' }}>
                  Price range
                </label>
                <select
                  value={form.price_range}
                  onChange={(e) => update('price_range', e.target.value)}
                  className="w-full px-4 py-2.5 border-2 rounded-lg text-sm"
                  style={{ borderColor: 'rgba(224, 110, 127, 0.25)', fontFamily: 'Montserrat, sans-serif' }}
                >
                  {priceChoices.map((c) => (
                    <option key={c.value} value={c.value}>
                      {c.label}
                    </option>
                  ))}
                </select>
              </div>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label className="text-xs block mb-1" style={{ fontFamily: 'Montserrat, sans-serif', color: '#666' }}>
                  Opening time
                </label>
                <input
                  type="time"
                  value={form.hours_open.length > 5 ? form.hours_open.slice(0, 5) : form.hours_open}
                  onChange={(e) => update('hours_open', e.target.value)}
                  className="w-full px-4 py-2.5 border-2 rounded-lg text-sm"
                  style={{ borderColor: 'rgba(224, 110, 127, 0.25)', fontFamily: 'Montserrat, sans-serif' }}
                />
              </div>
              <div>
                <label className="text-xs block mb-1" style={{ fontFamily: 'Montserrat, sans-serif', color: '#666' }}>
                  Closing time
                </label>
                <input
                  type="time"
                  value={form.hours_close.length > 5 ? form.hours_close.slice(0, 5) : form.hours_close}
                  onChange={(e) => update('hours_close', e.target.value)}
                  className="w-full px-4 py-2.5 border-2 rounded-lg text-sm"
                  style={{ borderColor: 'rgba(224, 110, 127, 0.25)', fontFamily: 'Montserrat, sans-serif' }}
                />
              </div>
            </div>
            <div>
              <label className="text-xs block mb-1" style={{ fontFamily: 'Montserrat, sans-serif', color: '#666' }}>
                Address
              </label>
              <input
                value={form.address}
                onChange={(e) => update('address', e.target.value)}
                className="w-full px-4 py-2.5 border-2 rounded-lg text-sm"
                style={{ borderColor: 'rgba(224, 110, 127, 0.25)', fontFamily: 'Montserrat, sans-serif' }}
              />
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label className="text-xs block mb-1" style={{ fontFamily: 'Montserrat, sans-serif', color: '#666' }}>
                  Phone
                </label>
                <input
                  value={form.phone}
                  onChange={(e) => update('phone', e.target.value)}
                  className="w-full px-4 py-2.5 border-2 rounded-lg text-sm"
                  style={{ borderColor: 'rgba(224, 110, 127, 0.25)', fontFamily: 'Montserrat, sans-serif' }}
                />
              </div>
              <div>
                <label className="text-xs block mb-1" style={{ fontFamily: 'Montserrat, sans-serif', color: '#666' }}>
                  Contact email
                </label>
                <input
                  type="email"
                  value={form.email}
                  onChange={(e) => update('email', e.target.value)}
                  className="w-full px-4 py-2.5 border-2 rounded-lg text-sm"
                  style={{ borderColor: 'rgba(224, 110, 127, 0.25)', fontFamily: 'Montserrat, sans-serif' }}
                />
              </div>
            </div>
            <div>
              <label className="text-xs block mb-1" style={{ fontFamily: 'Montserrat, sans-serif', color: '#666' }}>
                Website
              </label>
              <input
                type="url"
                placeholder="https://"
                value={form.website}
                onChange={(e) => update('website', e.target.value)}
                className="w-full px-4 py-2.5 border-2 rounded-lg text-sm"
                style={{ borderColor: 'rgba(224, 110, 127, 0.25)', fontFamily: 'Montserrat, sans-serif' }}
              />
            </div>

            {errors && (
              <div className="text-sm space-y-1" style={{ color: '#b91c1c', fontFamily: 'Montserrat, sans-serif' }}>
                {Object.entries(errors).map(([k, msgs]) => (
                  <div key={k}>
                    {k !== '__all__' && <strong>{k}: </strong>}
                    {(msgs as string[]).join(' ')}
                  </div>
                ))}
              </div>
            )}

            <div className="flex gap-3 pt-2">
              <button
                type="submit"
                disabled={saving}
                title="Save restaurant profile"
                className="px-6 py-3 rounded-lg text-sm text-white disabled:opacity-60"
                style={{ backgroundColor: '#E06E7F', border: 'none', cursor: 'pointer', fontFamily: 'Montserrat, sans-serif' }}
              >
                {saving ? 'Saving…' : 'Save'}
              </button>
              <button
                type="button"
                onClick={onBack}
                title="Cancel and return to previous page"
                className="px-6 py-3 rounded-lg text-sm"
                style={{
                  backgroundColor: 'white',
                  border: '2px solid rgba(224, 110, 127, 0.3)',
                  color: '#666',
                  cursor: 'pointer',
                  fontFamily: 'Montserrat, sans-serif',
                }}
              >
                Cancel
              </button>
            </div>
          </form>
        )}
      </main>
      <Footer />
    </div>
  );
}
