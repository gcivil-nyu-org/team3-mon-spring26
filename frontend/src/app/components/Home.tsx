import { Footer } from './Footer';

export function Home({ onSignInClick, onSignUpClick }: { onSignInClick: () => void; onSignUpClick: () => void }) {
  return (
    <div className="size-full flex flex-col overflow-y-auto" style={{ backgroundColor: '#FFF9F5' }}>
      {/* Navigation Bar */}
      <nav className="w-full px-8 py-8 flex items-center justify-between">
        <h1 className="text-2xl" style={{ 
          fontFamily: 'Montserrat, sans-serif',
          color: '#E06E7F'
        }}>
          nomz
        </h1>
        
        <div className="flex items-center gap-4">
          <button
            onClick={onSignInClick}
            className="px-5 py-2 rounded-lg transition-all text-sm"
            title="Log In"
            style={{ 
              backgroundColor: 'transparent',
              color: '#E06E7F',
              border: '2px solid #E06E7F',
              fontFamily: 'Montserrat, sans-serif'
            }}
            onMouseEnter={(e) => { e.currentTarget.style.backgroundColor = 'rgba(224, 110, 127, 0.1)'; e.currentTarget.style.transform = 'translateY(-2px)'; }}
            onMouseLeave={(e) => { e.currentTarget.style.backgroundColor = 'transparent'; e.currentTarget.style.transform = 'translateY(0)'; }}
          >
            Log In
          </button>
          
          <button
            onClick={onSignUpClick}
            className="px-5 py-2 rounded-lg transition-all text-sm"
            title="Sign Up"
            style={{ 
              backgroundColor: '#E06E7F',
              color: 'white',
              fontFamily: 'Montserrat, sans-serif'
            }}
            onMouseEnter={(e) => e.currentTarget.style.transform = 'translateY(-2px)'}
            onMouseLeave={(e) => e.currentTarget.style.transform = 'translateY(0)'}
          >
            Sign Up
          </button>
        </div>
      </nav>

      {/* Main Content */}
      <main className="w-full py-20 px-8">
        <div className="max-w-3xl mx-auto text-center">
          <h2 className="text-3xl mb-8" style={{ 
            fontFamily: 'Montserrat, sans-serif',
            color: '#E06E7F'
          }}>
            Welcome to nomz
          </h2>
          
          <p className="text-base leading-relaxed mb-16 max-w-2xl mx-auto" style={{ 
            fontFamily: 'Montserrat, sans-serif',
            color: '#333'
          }}>
            Discover amazing restaurants and delicious food near you. Whether you're a food lover 
            looking for your next favorite spot or a restaurant owner wanting to showcase your culinary 
            creations, nomz is here to connect diners with the best dining experiences.
          </p>
          
          <div className="grid grid-cols-1 md:grid-cols-2 gap-8 max-w-2xl mx-auto">
            <div className="p-8 rounded-lg" style={{ 
              backgroundColor: 'rgba(224, 110, 127, 0.08)'
            }}>
              <h3 className="text-lg mb-4" style={{ 
                fontFamily: 'Montserrat, sans-serif',
                color: '#E06E7F'
              }}>
                For Diners
              </h3>
              <p className="text-sm leading-relaxed" style={{ 
                fontFamily: 'Montserrat, sans-serif',
                color: '#666'
              }}>
                Find your next favorite restaurant, read reviews, and explore menus from local eateries.
              </p>
            </div>
            
            <div className="p-8 rounded-lg" style={{ 
              backgroundColor: 'rgba(224, 110, 127, 0.08)'
            }}>
              <h3 className="text-lg mb-4" style={{ 
                fontFamily: 'Montserrat, sans-serif',
                color: '#E06E7F'
              }}>
                For Restaurants
              </h3>
              <p className="text-sm leading-relaxed" style={{ 
                fontFamily: 'Montserrat, sans-serif',
                color: '#666'
              }}>
                Showcase your menu, connect with food lovers, and grow your business with nomz.
              </p>
            </div>
          </div>
        </div>
      </main>

      {/* Developers Section */}
      <section className="w-full py-20 px-8 mt-16" style={{ 
        backgroundColor: 'rgba(224, 110, 127, 0.04)'
      }}>
        <div className="max-w-3xl mx-auto">
          <h2 className="text-2xl mb-6 text-center" style={{ 
            fontFamily: 'Montserrat, sans-serif',
            color: '#E06E7F'
          }}>
            Meet the Developers
          </h2>
          
          <p className="text-sm text-center mb-16 leading-relaxed max-w-xl mx-auto" style={{ 
            fontFamily: 'Montserrat, sans-serif',
            color: '#666'
          }}>
            nomz was created by a passionate team of developers who love food and technology.
          </p>

          <div className="flex flex-col gap-8 items-center">
            {/* First Row - 3 Developers */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-8 max-w-4xl">
              <div className="p-6 rounded-lg text-center" style={{ 
                backgroundColor: '#FFF9F5'
              }}>
                <div className="w-20 h-20 rounded-full mx-auto mb-5" style={{ 
                  backgroundColor: 'rgba(224, 110, 127, 0.15)'
                }}></div>
                <h3 className="text-base mb-2" style={{ 
                  fontFamily: 'Montserrat, sans-serif',
                  color: '#E06E7F'
                }}>
                  Ananya Agarwal
                </h3>
                <p className="text-xs" style={{ 
                  fontFamily: 'Montserrat, sans-serif',
                  color: '#666'
                }}>
                  UI/UX Designer and Developer
                </p>
              </div>

              <div className="p-6 rounded-lg text-center" style={{ 
                backgroundColor: '#FFF9F5'
              }}>
                <div className="w-20 h-20 rounded-full mx-auto mb-5" style={{ 
                  backgroundColor: 'rgba(224, 110, 127, 0.15)'
                }}></div>
                <h3 className="text-base mb-2" style={{ 
                  fontFamily: 'Montserrat, sans-serif',
                  color: '#E06E7F'
                }}>
                  Gurleen Kaur
                </h3>
                <p className="text-xs" style={{ 
                  fontFamily: 'Montserrat, sans-serif',
                  color: '#666'
                }}>
                  Software Developer
                </p>
              </div>

              <div className="p-6 rounded-lg text-center" style={{ 
                backgroundColor: '#FFF9F5'
              }}>
                <div className="w-20 h-20 rounded-full mx-auto mb-5" style={{ 
                  backgroundColor: 'rgba(224, 110, 127, 0.15)'
                }}></div>
                <h3 className="text-base mb-2" style={{ 
                  fontFamily: 'Montserrat, sans-serif',
                  color: '#E06E7F'
                }}>
                  Darsh Shani
                </h3>
                <p className="text-xs" style={{ 
                  fontFamily: 'Montserrat, sans-serif',
                  color: '#666'
                }}>
                  Data Engineer and Developer
                </p>
              </div>
            </div>

            {/* Second Row - 2 Developers */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-8 max-w-2xl">
              <div className="p-6 rounded-lg text-center" style={{ 
                backgroundColor: '#FFF9F5'
              }}>
                <div className="w-20 h-20 rounded-full mx-auto mb-5" style={{ 
                  backgroundColor: 'rgba(224, 110, 127, 0.15)'
                }}></div>
                <h3 className="text-base mb-2" style={{ 
                  fontFamily: 'Montserrat, sans-serif',
                  color: '#E06E7F'
                }}>
                  Vritika Srivastava
                </h3>
                <p className="text-xs" style={{ 
                  fontFamily: 'Montserrat, sans-serif',
                  color: '#666'
                }}>
                  Software Developer
                </p>
              </div>

              <div className="p-6 rounded-lg text-center" style={{ 
                backgroundColor: '#FFF9F5'
              }}>
                <div className="w-20 h-20 rounded-full mx-auto mb-5" style={{ 
                  backgroundColor: 'rgba(224, 110, 127, 0.15)'
                }}></div>
                <h3 className="text-base mb-2" style={{ 
                  fontFamily: 'Montserrat, sans-serif',
                  color: '#E06E7F'
                }}>
                  Ashik M John
                </h3>
                <p className="text-xs" style={{ 
                  fontFamily: 'Montserrat, sans-serif',
                  color: '#666'
                }}>
                  Software Developer
                </p>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Footer */}
      <Footer />
    </div>
  );
}