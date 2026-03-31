// Stripe Checkout integration for Team and Business tiers.
//
// SETUP REQUIRED:
// 1. Replace STRIPE_PUBLISHABLE_KEY with your Stripe publishable key.
// 2. Create two Stripe Price objects (Team: $999/yr, Business: $4,999/yr)
//    and set their IDs below.
// 3. The Cloudflare Worker webhook endpoint handles license key generation
//    after successful payment.

var STRIPE_PUBLISHABLE_KEY = 'pk_live_REPLACE_WITH_YOUR_KEY';

var PRICE_IDS = {
  team:     'price_REPLACE_WITH_TEAM_PRICE_ID',
  business: 'price_REPLACE_WITH_BUSINESS_PRICE_ID'
};

// Checkout success/cancel URLs — update to your domain.
var SUCCESS_URL = 'https://atested.com/success.html?session_id={CHECKOUT_SESSION_ID}';
var CANCEL_URL  = 'https://atested.com/pricing.html';

function checkout(tier) {
  var priceId = PRICE_IDS[tier];
  if (!priceId || priceId.indexOf('REPLACE') !== -1) {
    alert('Stripe is not configured yet. See deployment instructions.');
    return;
  }

  // Load Stripe.js if not already loaded.
  if (typeof Stripe === 'undefined') {
    var script = document.createElement('script');
    script.src = 'https://js.stripe.com/v3/';
    script.onload = function () { redirectToCheckout(priceId); };
    document.head.appendChild(script);
  } else {
    redirectToCheckout(priceId);
  }
}

function redirectToCheckout(priceId) {
  var stripe = Stripe(STRIPE_PUBLISHABLE_KEY);
  stripe.redirectToCheckout({
    lineItems: [{ price: priceId, quantity: 1 }],
    mode: 'payment',
    successUrl: SUCCESS_URL,
    cancelUrl: CANCEL_URL
  }).then(function (result) {
    if (result.error) {
      alert(result.error.message);
    }
  });
}
