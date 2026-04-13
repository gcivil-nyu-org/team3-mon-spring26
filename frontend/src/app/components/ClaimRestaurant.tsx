import { useCallback, useEffect, useState } from "react";
import { Footer } from "./Footer";
import { apiFetch } from "../api";

type ClaimRestaurantRow = {
  id: number;
  restaurant_id: number;
  restaurant_name: string;
  created_at: string;
  status: string;
};

type RestaurantOption = {
  id: number;
  name: string;
  address: string;
  zip_code: string;
};

export function ClaimRestaurant({
  onBack,
  onSubmitted,
}: {
  onBack: () => void;
  onSubmitted?: () => void;
}) {
  const [loading, setLoading] = useState(true);
  const [fetchError, setFetchError] = useState<string | null>(null);
  const [eligible, setEligible] = useState(true);
  const [hasRestaurant, setHasRestaurant] = useState(false);
  const [activeClaim, setActiveClaim] = useState<ClaimRestaurantRow | null>(null);
  const [recentClaims, setRecentClaims] = useState<ClaimRestaurantRow[]>([]);
  const [restaurants, setRestaurants] = useState<RestaurantOption[]>([]);

  const [searchInput, setSearchInput] = useState("");
  const [appliedSearch, setAppliedSearch] = useState("");

  const [restaurantId, setRestaurantId] = useState("");
  const [businessEmail, setBusinessEmail] = useState("");
  const [contactPhone, setContactPhone] = useState("");
  const [proofDetails, setProofDetails] = useState("");

  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [fieldErrors, setFieldErrors] = useState<Record<string, string[]>>({});
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  const load = useCallback(async (search: string) => {
    setLoading(true);
    setFetchError(null);
    try {
      const q = new URLSearchParams();
      if (search.trim()) q.set("search", search.trim());
      const path = q.toString() ? `/api/restaurant-claim/?${q}` : "/api/restaurant-claim/";
      const res = await apiFetch(path);
      if (res.status === 403) {
        const data = (await res.json().catch(() => ({}))) as { error?: string };
        setEligible(false);
        setFetchError(data.error ?? "You do not have permission to claim a listing.");
        setLoading(false);
        return;
      }
      if (!res.ok) {
        setFetchError(`Could not load claim page (${res.status}).`);
        setLoading(false);
        return;
      }
      const data = (await res.json()) as {
        eligible?: boolean;
        has_restaurant?: boolean;
        active_claim?: ClaimRestaurantRow | null;
        recent_claims?: ClaimRestaurantRow[];
        restaurants?: RestaurantOption[];
      };
      setEligible(data.eligible !== false);
      setHasRestaurant(!!data.has_restaurant);
      setActiveClaim(data.active_claim ?? null);
      setRecentClaims(data.recent_claims ?? []);
      setRestaurants(data.restaurants ?? []);
    } catch {
      setFetchError(
        "Network error. Set VITE_API_BASE_URL to your Django origin (e.g. http://127.0.0.1:8000) when using the Vite dev server."
      );
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load(appliedSearch);
  }, [load, appliedSearch]);

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    setAppliedSearch(searchInput);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (activeClaim || hasRestaurant || !eligible) return;
    setSubmitting(true);
    setSubmitError(null);
    setFieldErrors({});
    setSuccessMessage(null);
    try {
      const res = await apiFetch("/api/restaurant-claim/", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          restaurant_id: restaurantId,
          business_email: businessEmail,
          contact_phone: contactPhone,
          proof_details: proofDetails,
          search: appliedSearch,
        }),
      });
      const data = (await res.json().catch(() => ({}))) as {
        success?: boolean;
        message?: string;
        error?: string;
        errors?: Record<string, string[]>;
      };
      if (res.ok && data.success) {
        setSuccessMessage(data.message ?? "Claim submitted.");
        setRestaurantId("");
        setProofDetails("");
        await load(appliedSearch);
        onSubmitted?.();
        return;
      }
      if (data.error) {
        setSubmitError(data.error);
      } else if (data.errors) {
        setFieldErrors(data.errors);
        const nf = data.errors.non_field;
        if (nf?.length) {
          setSubmitError(nf.join(" "));
        }
      } else {
        setSubmitError("Could not submit claim.");
      }
    } catch {
      setSubmitError("Network error while submitting.");
    } finally {
      setSubmitting(false);
    }
  };

  const formDisabled = !!activeClaim || hasRestaurant || !eligible || loading;

  const statusBadge = (status: string) => {
    if (status === "approved") {
      return (
        <span className="text-xs px-2 py-1 rounded" style={{ backgroundColor: "#d1fae5", color: "#065f46" }}>
          Approved
        </span>
      );
    }
    if (status === "rejected") {
      return (
        <span className="text-xs px-2 py-1 rounded" style={{ backgroundColor: "#fee2e2", color: "#991b1b" }}>
          Rejected
        </span>
      );
    }
    return (
      <span className="text-xs px-2 py-1 rounded" style={{ backgroundColor: "#fef3c7", color: "#92400e" }}>
        Pending
      </span>
    );
  };

  return (
    <div className="size-full flex flex-col overflow-y-auto" style={{ backgroundColor: "#FFF9F5" }}>
      <nav className="w-full px-8 py-4 flex items-center justify-between shrink-0">
        <div className="flex items-center gap-6">
          <button
            type="button"
            onClick={onBack}
            className="text-xl transition-all p-2 rounded-lg"
            title="Back"
            onMouseEnter={(e) => {
              e.currentTarget.style.backgroundColor = "rgba(224, 110, 127, 0.1)";
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.backgroundColor = "transparent";
            }}
            style={{
              backgroundColor: "transparent",
              border: "none",
              cursor: "pointer",
              color: "#E06E7F",
              fontWeight: "normal",
            }}
          >
            ←
          </button>
          <h1
            className="text-2xl"
            style={{
              fontFamily: "Montserrat, sans-serif",
              color: "#E06E7F",
            }}
          >
            nomz
          </h1>
        </div>
      </nav>

      <main className="w-full py-8 px-8 flex-1">
        <div className="max-w-3xl mx-auto">
          <div
            className="rounded-lg overflow-hidden mb-6"
            style={{ border: "2px solid rgba(224, 110, 127, 0.15)", backgroundColor: "white" }}
          >
            <div className="px-6 py-4" style={{ backgroundColor: "rgba(224, 110, 127, 0.08)", borderBottom: "1px solid rgba(224, 110, 127, 0.15)" }}>
              <h2 className="text-lg m-0" style={{ fontFamily: "Montserrat, sans-serif", color: "#E06E7F" }}>
                Claim an existing restaurant listing
              </h2>
            </div>
            <div className="p-6">
              <p className="text-sm mb-4 m-0" style={{ fontFamily: "Montserrat, sans-serif", color: "#666" }}>
                If your restaurant already exists in Nomz data, submit a claim and our team will verify ownership before
                granting access.
              </p>

              {fetchError && (
                <div className="mb-4 p-3 rounded-lg text-sm" style={{ backgroundColor: "#fee2e2", color: "#991b1b" }}>
                  {fetchError}
                </div>
              )}

              {hasRestaurant && !fetchError && (
                <div className="mb-4 p-3 rounded-lg text-sm" style={{ backgroundColor: "#e0f2fe", color: "#075985" }}>
                  You already have a restaurant assigned to your account.
                </div>
              )}

              {activeClaim && (
                <div className="mb-4 p-3 rounded-lg text-sm" style={{ backgroundColor: "#fef3c7", color: "#92400e" }}>
                  You currently have a pending claim for <strong>{activeClaim.restaurant_name}</strong>. We will review it
                  before assigning ownership.
                </div>
              )}

              {successMessage && (
                <div className="mb-4 p-3 rounded-lg text-sm" style={{ backgroundColor: "#d1fae5", color: "#065f46" }}>
                  {successMessage}
                </div>
              )}

              <form onSubmit={handleSearch} className="mb-6">
                <label className="block text-sm mb-2" style={{ fontFamily: "Montserrat, sans-serif", color: "#333" }}>
                  Search restaurant
                </label>
                <div className="flex gap-2 flex-wrap">
                  <input
                    type="text"
                    value={searchInput}
                    onChange={(e) => setSearchInput(e.target.value)}
                    placeholder="Search by name, address, or ZIP"
                    className="flex-1 min-w-[200px] px-4 py-2 rounded-lg border-2 text-sm focus:outline-none"
                    style={{
                      borderColor: "rgba(224, 110, 127, 0.25)",
                      fontFamily: "Montserrat, sans-serif",
                    }}
                    disabled={loading}
                  />
                  <button
                    type="submit"
                    title="Search for restaurants"
                    className="px-5 py-2 rounded-lg text-sm transition-all"
                    style={{
                      fontFamily: "Montserrat, sans-serif",
                      backgroundColor: "white",
                      color: "#E06E7F",
                      border: "2px solid rgba(224, 110, 127, 0.4)",
                      cursor: loading ? "wait" : "pointer",
                    }}
                    disabled={loading}
                  >
                    Search
                  </button>
                </div>
              </form>

              {loading ? (
                <p className="text-sm" style={{ fontFamily: "Montserrat, sans-serif", color: "#999" }}>
                  Loading…
                </p>
              ) : (
                <form onSubmit={handleSubmit}>
                  {submitError && (
                    <div className="mb-4 p-3 rounded-lg text-sm" style={{ backgroundColor: "#fee2e2", color: "#991b1b" }}>
                      {submitError}
                    </div>
                  )}

                  <div className="mb-4">
                    <label className="block text-sm mb-2" style={{ fontFamily: "Montserrat, sans-serif", color: "#333" }}>
                      Restaurant
                    </label>
                    <select
                      required
                      value={restaurantId}
                      onChange={(e) => setRestaurantId(e.target.value)}
                      className="w-full px-4 py-2 rounded-lg border-2 text-sm focus:outline-none"
                      style={{
                        borderColor: "rgba(224, 110, 127, 0.25)",
                        fontFamily: "Montserrat, sans-serif",
                        backgroundColor: "white",
                      }}
                      disabled={formDisabled}
                    >
                      <option value="">Select your restaurant…</option>
                      {restaurants.map((r) => (
                        <option key={r.id} value={r.id}>
                          {r.name}
                          {r.address ? ` — ${r.address}` : ""}
                          {r.zip_code ? ` (${r.zip_code})` : ""}
                        </option>
                      ))}
                    </select>
                    <p className="text-xs mt-1 m-0" style={{ fontFamily: "Montserrat, sans-serif", color: "#888" }}>
                      Pick your restaurant from unclaimed listings. Use search to narrow results.
                    </p>
                    {(fieldErrors.restaurant ?? []).map((err) => (
                      <p key={err} className="text-xs text-red-600 m-0 mt-1">
                        {err}
                      </p>
                    ))}
                  </div>

                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
                    <div>
                      <label className="block text-sm mb-2" style={{ fontFamily: "Montserrat, sans-serif", color: "#333" }}>
                        Business email
                      </label>
                      <input
                        type="email"
                        value={businessEmail}
                        onChange={(e) => setBusinessEmail(e.target.value)}
                        placeholder="owner@restaurant.com"
                        className="w-full px-4 py-2 rounded-lg border-2 text-sm focus:outline-none"
                        style={{
                          borderColor: "rgba(224, 110, 127, 0.25)",
                          fontFamily: "Montserrat, sans-serif",
                        }}
                        disabled={formDisabled}
                      />
                      {(fieldErrors.business_email ?? []).map((err) => (
                        <p key={err} className="text-xs text-red-600 m-0 mt-1">
                          {err}
                        </p>
                      ))}
                    </div>
                    <div>
                      <label className="block text-sm mb-2" style={{ fontFamily: "Montserrat, sans-serif", color: "#333" }}>
                        Business phone
                      </label>
                      <input
                        type="text"
                        value={contactPhone}
                        onChange={(e) => setContactPhone(e.target.value)}
                        placeholder="+1 212-555-1234"
                        className="w-full px-4 py-2 rounded-lg border-2 text-sm focus:outline-none"
                        style={{
                          borderColor: "rgba(224, 110, 127, 0.25)",
                          fontFamily: "Montserrat, sans-serif",
                        }}
                        disabled={formDisabled}
                      />
                      {(fieldErrors.contact_phone ?? []).map((err) => (
                        <p key={err} className="text-xs text-red-600 m-0 mt-1">
                          {err}
                        </p>
                      ))}
                    </div>
                  </div>

                  <div className="mb-6">
                    <label className="block text-sm mb-2" style={{ fontFamily: "Montserrat, sans-serif", color: "#333" }}>
                      Verification details
                    </label>
                    <textarea
                      value={proofDetails}
                      onChange={(e) => setProofDetails(e.target.value)}
                      rows={4}
                      placeholder="Share proof like website manager email match, business license number, menu system access, or public listing links."
                      className="w-full px-4 py-2 rounded-lg border-2 text-sm focus:outline-none resize-y min-h-[100px]"
                      style={{
                        borderColor: "rgba(224, 110, 127, 0.25)",
                        fontFamily: "Montserrat, sans-serif",
                      }}
                      disabled={formDisabled}
                    />
                    {(fieldErrors.proof_details ?? []).map((err) => (
                      <p key={err} className="text-xs text-red-600 m-0 mt-1">
                        {err}
                      </p>
                    ))}
                  </div>

                  <div className="flex flex-wrap gap-3">
                    <button
                      type="submit"
                      title="Submit restaurant ownership claim"
                      className="px-6 py-2 rounded-lg text-sm transition-all"
                      style={{
                        fontFamily: "Montserrat, sans-serif",
                        backgroundColor: formDisabled ? "#ccc" : "#E06E7F",
                        color: "white",
                        border: "none",
                        cursor: formDisabled || submitting ? "not-allowed" : "pointer",
                      }}
                      disabled={formDisabled || submitting}
                    >
                      {submitting ? "Submitting…" : "Submit ownership claim"}
                    </button>
                    <button
                      type="button"
                      onClick={onBack}
                      title="Return to dashboard"
                      className="px-6 py-2 rounded-lg text-sm transition-all"
                      style={{
                        fontFamily: "Montserrat, sans-serif",
                        backgroundColor: "white",
                        color: "#E06E7F",
                        border: "2px solid rgba(224, 110, 127, 0.35)",
                        cursor: "pointer",
                      }}
                    >
                      Back to dashboard
                    </button>
                  </div>
                </form>
              )}
            </div>
          </div>

          {!loading && recentClaims.length > 0 && (
            <div
              className="rounded-lg overflow-hidden"
              style={{ border: "2px solid rgba(224, 110, 127, 0.15)", backgroundColor: "white" }}
            >
              <div className="px-6 py-3" style={{ backgroundColor: "#E06E7F", color: "white" }}>
                <h3 className="text-sm m-0" style={{ fontFamily: "Montserrat, sans-serif" }}>
                  Recent claim activity
                </h3>
              </div>
              <ul className="list-none m-0 p-0">
                {recentClaims.map((claim) => (
                  <li
                    key={claim.id}
                    className="flex justify-between items-center gap-4 px-6 py-4"
                    style={{
                      borderBottom: "1px solid rgba(224, 110, 127, 0.1)",
                      fontFamily: "Montserrat, sans-serif",
                    }}
                  >
                    <span className="text-sm" style={{ color: "#333" }}>
                      <strong>{claim.restaurant_name}</strong>
                      <span className="text-muted-foreground text-xs ml-2" style={{ color: "#888" }}>
                        submitted{" "}
                        {new Date(claim.created_at).toLocaleDateString("en-US", {
                          month: "short",
                          day: "numeric",
                          year: "numeric",
                        })}
                      </span>
                    </span>
                    {statusBadge(claim.status)}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      </main>

      <Footer />
    </div>
  );
}
