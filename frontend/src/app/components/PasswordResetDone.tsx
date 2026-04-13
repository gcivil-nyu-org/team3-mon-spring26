export function PasswordResetDone({ onBack }: { onBack: () => void }) {
  return (
    <div className="size-full flex flex-col items-center justify-center" style={{ backgroundColor: '#FFF9F5' }}>
      <div className="w-full max-w-md px-8">
        {/* Card */}
        <div className="rounded-lg p-8 text-center" style={{
          backgroundColor: 'white',
          border: '2px solid rgba(224, 110, 127, 0.1)'
        }}>
          {/* Icon */}
          <div className="mb-6 text-5xl">
            ✉️
          </div>

          {/* Header */}
          <div className="mb-6">
            <h2 className="text-3xl mb-4" style={{
              fontFamily: 'Montserrat, sans-serif',
              color: '#E06E7F',
              fontWeight: '600'
            }}>
              Check your email
            </h2>
          </div>

          {/* Message */}
          <p style={{
            fontFamily: 'Montserrat, sans-serif',
            color: '#666',
            fontSize: '14px',
            lineHeight: '1.6',
            marginBottom: '24px'
          }}>
            If an account exists with that email, you will receive a password reset link shortly. Check your spam folder if you don't see it.
          </p>

          {/* Button */}
          <button
            onClick={onBack}
            className="w-full py-3 rounded-lg font-medium transition-all text-white"
            title="Back to log in"
            style={{
              backgroundColor: '#E06E7F',
              cursor: 'pointer',
              fontFamily: 'Montserrat, sans-serif',
              fontSize: '14px',
              border: 'none'
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.backgroundColor = '#d1596d';
              e.currentTarget.style.transform = 'translateY(-2px)';
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.backgroundColor = '#E06E7F';
              e.currentTarget.style.transform = 'translateY(0)';
            }}
          >
            Back to log in
          </button>
        </div>
      </div>
    </div>
  );
}
