export function PasswordResetComplete({ onLoginClick }: { onLoginClick: () => void }) {
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
            ✓
          </div>

          {/* Header */}
          <div className="mb-6">
            <h2 className="text-3xl mb-4" style={{
              fontFamily: 'Montserrat, sans-serif',
              color: '#E06E7F',
              fontWeight: '600'
            }}>
              Password reset complete
            </h2>
          </div>

          {/* Message */}
          <p style={{
            fontFamily: 'Montserrat, sans-serif',
            color: '#666',
            fontSize: '14px',
            marginBottom: '24px'
          }}>
            Your password has been successfully changed. You can now log in with your new password.
          </p>

          {/* Button */}
          <button
            onClick={onLoginClick}
            className="w-full py-3 rounded-lg font-medium transition-all text-white"
            title="Log in"
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
            Log in
          </button>
        </div>
      </div>
    </div>
  );
}
