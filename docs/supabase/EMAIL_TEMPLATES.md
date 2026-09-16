# Supabase Email Templates

Configure at: Supabase Dashboard ��� Authentication → Email Templates

---

## Confirm Signup

**Subject:**
```
Confirm your manga-dl account
```

**Body (HTML):**
```html
<div style="font-family:sans-serif;max-width:480px;margin:0 auto;background:#09090b;color:#fafafa;padding:40px;border-radius:16px;border:1px solid #ffffff18">
  <h1 style="font-size:24px;font-weight:900;text-transform:uppercase;letter-spacing:0.05em;margin:0 0 8px">manga-dl</h1>
  <p style="color:#ffffff60;font-size:12px;text-transform:uppercase;letter-spacing:0.2em;margin:0 0 32px">Your manga library, everywhere</p>

  <p style="font-size:15px;color:#ffffff99;margin:0 0 24px">Click the button below to confirm your email address and activate your account.</p>

  <a href="{{ .ConfirmationURL }}" style="display:block;text-align:center;background:#dc2626;color:#fff;font-weight:900;text-transform:uppercase;letter-spacing:0.1em;font-size:13px;padding:14px 24px;border-radius:12px;text-decoration:none">
    Confirm Email
  </a>

  <p style="margin:24px 0 0;font-size:12px;color:#ffffff30;text-align:center">
    Link expires in 24 hours. If you didn't create this account, ignore this email.
  </p>
</div>
```

---

## Reset Password

**Subject:**
```
Reset your manga-dl password
```

**Body (HTML):**
```html
<div style="font-family:sans-serif;max-width:480px;margin:0 auto;background:#09090b;color:#fafafa;padding:40px;border-radius:16px;border:1px solid #ffffff18">
  <h1 style="font-size:24px;font-weight:900;text-transform:uppercase;letter-spacing:0.05em;margin:0 0 8px">manga-dl</h1>
  <p style="color:#ffffff60;font-size:12px;text-transform:uppercase;letter-spacing:0.2em;margin:0 0 32px">Your manga library, everywhere</p>

  <p style="font-size:15px;color:#ffffff99;margin:0 0 24px">We received a request to reset your password. Click below to choose a new one.</p>

  <a href="{{ .ConfirmationURL }}" style="display:block;text-align:center;background:#dc2626;color:#fff;font-weight:900;text-transform:uppercase;letter-spacing:0.1em;font-size:13px;padding:14px 24px;border-radius:12px;text-decoration:none">
    Reset Password
  </a>

  <p style="margin:24px 0 0;font-size:12px;color:#ffffff30;text-align:center">
    Link expires in 1 hour. If you didn't request this, ignore this email — your password won't change.
  </p>
</div>
```

---

## Magic Link

**Subject:**
```
Your manga-dl sign-in link
```

**Body (HTML):**
```html
<div style="font-family:sans-serif;max-width:480px;margin:0 auto;background:#09090b;color:#fafafa;padding:40px;border-radius:16px;border:1px solid #ffffff18">
  <h1 style="font-size:24px;font-weight:900;text-transform:uppercase;letter-spacing:0.05em;margin:0 0 8px">manga-dl</h1>
  <p style="color:#ffffff60;font-size:12px;text-transform:uppercase;letter-spacing:0.2em;margin:0 0 32px">Your manga library, everywhere</p>

  <p style="font-size:15px;color:#ffffff99;margin:0 0 24px">Click the link below to sign in. No password needed.</p>

  <a href="{{ .ConfirmationURL }}" style="display:block;text-align:center;background:#dc2626;color:#fff;font-weight:900;text-transform:uppercase;letter-spacing:0.1em;font-size:13px;padding:14px 24px;border-radius:12px;text-decoration:none">
    Sign In
  </a>

  <p style="margin:24px 0 0;font-size:12px;color:#ffffff30;text-align:center">
    Link expires in 1 hour. If you didn't request this, ignore this email.
  </p>
</div>
```

---

## Notes

- `{{ .ConfirmationURL }}` is Supabase's template variable — do not change it
- The redirect after confirmation goes to `https://manga-dl.web.app/login` (configured in `Register.tsx` and in Dashboard → Redirect URLs)
- Test emails via: Supabase Dashboard → Authentication → Users → Invite user
