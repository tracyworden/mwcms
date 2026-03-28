# Implementation Plan: React Native TV App

## Overview

Build a React Native TV application in `tv-app/` targeting Android TV, Fire TV, and Apple TV. The app provides a simplified three-screen flow (Login → Browse → Player) optimized for older adults using D-pad remotes. A small backend change to `app/api/auth/router.py` is required first to support 30-day TV tokens.

Backend: Python (FastAPI). TV App: TypeScript (React Native with react-native-tvos).

## Tasks

- [ ] 1. Backend: Add `client_type` field to login endpoint
  - [ ] 1.1 Modify `LoginRequest` in `app/api/auth/router.py` to add optional `client_type: str | None = None` field, and update the `login` function to issue a 30-day JWT when `client_type == "tv"`, otherwise keep the existing 24-hour expiry
    - Add `client_type: str | None = None` to `LoginRequest`
    - Change expiry logic: `timedelta(days=30) if body.client_type == "tv" else timedelta(hours=24)`
    - Existing web frontend requests (without `client_type`) must remain unaffected
    - _Requirements: 1.12_

  - [ ]* 1.2 Write property test for backend `client_type=tv` 30-day token (Python/Hypothesis)
    - **Property 6: Backend client_type=tv yields 30-day token**
    - Create `tests/property/test_auth_client_type.py`
    - Generate random valid usernames, call login with and without `client_type="tv"`, decode JWT, verify `exp - iat` is ~30 days or ~24 hours (60s tolerance)
    - **Validates: Requirements 1.12**

- [ ] 2. Checkpoint — Verify backend change
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 3. Initialize React Native TV project and configure build targets
  - [ ] 3.1 Scaffold the `tv-app/` project using `react-native-tvos` template
    - Initialize project in `tv-app/` directory
    - Install dependencies: `react-native-tvos`, `react-native-keychain`, `axios`, `react-native-video`, `@react-navigation/native`, `@react-navigation/native-stack`, `fast-check` (dev), `jest` (dev), `@types/jest` (dev)
    - Configure `tsconfig.json` with strict mode
    - Set Android `minSdkVersion` to 21 (API level 21 / Lollipop) for Android TV and Fire TV
    - Set tvOS deployment target to 15.0 for Apple TV
    - _Requirements: 7.1, 7.2, 7.3, 7.4_

- [ ] 4. Create theme constants and shared types
  - [ ] 4.1 Create `tv-app/src/theme/constants.ts` with `FONT_SIZE`, `FOCUS`, and `COLORS` constants as defined in the design document
    - `FONT_SIZE`: title=32, header=28, body=24
    - `FOCUS`: borderWidth=3, scaleFactor=1.05, minTargetSize=48
    - `COLORS`: background="#121212", surface="#1E1E1E", text="#F5F5F5", textSecondary="#BDBDBD", focusBorder="#64B5F6", error="#EF9A9A", accent="#90CAF9"
    - _Requirements: 6.1, 6.2, 6.5, 6.6_

  - [ ]* 4.2 Write property test for theme accessibility constants
    - **Property 13: Theme constants meet accessibility minimums**
    - Verify background luminance ≤ 20%, text luminance ≥ 80%, body font ≥ 24, header ≥ 28, title ≥ 32, min target ≥ 48dp, focus border ≥ 3dp, scale ≥ 1.05
    - **Validates: Requirements 6.1, 6.2, 6.5, 6.6**

  - [ ] 4.3 Create `tv-app/src/types/media.ts` with shared type definitions compatible with `frontend/src/types/media.ts`
    - `MediaItemSummary`, `MediaItemDetail`, `MediaListResponse`, `YearsResponse`, `LoginRequest`, `LoginResponse`
    - TV app's `MediaItemDetail` sets `metadata: null` and `transcript: null` (TV app ignores these)
    - _Requirements: 7.5_

  - [ ]* 4.4 Write property test for type definition structural compatibility
    - **Property 14: Type definition structural compatibility**
    - Verify that TV app types share the same field names and compatible types as web frontend types for `MediaItemSummary`, `MediaListResponse`, `YearsResponse`
    - **Validates: Requirements 7.5**

  - [ ] 4.5 Create `tv-app/src/types/navigation.ts` with `RootStackParamList` (Login, Browse, Player) and `tv-app/src/types/auth.ts` with `DecodedJWT` interface
    - _Requirements: 6.3_

  - [ ] 4.6 Create `tv-app/src/utils/formatYearLabel.ts` utility function
    - Returns `"Unknown Year"` for `"unknown_year"`, input unchanged otherwise
    - _Requirements: 2.1_

  - [ ]* 4.7 Write property test for year label formatting
    - **Property 16: Year label formatting**
    - Generate random strings with fast-check, verify `formatYearLabel("unknown_year") === "Unknown Year"` and `formatYearLabel(other) === other` for all other inputs
    - **Validates: Requirements 2.1**

- [ ] 5. Implement service modules (AuthManager, ApiClient, error handling)
  - [ ] 5.1 Create `tv-app/src/services/errors.ts` with `AppError` interface, `AppErrorKind` type, and `classifyError` function as defined in the design
    - Classify axios errors into: network, unauthorized, unavailable, not_found, unknown
    - Map each to the correct user-facing message string per requirements
    - _Requirements: 8.1, 8.2, 8.4_

  - [ ] 5.2 Create `tv-app/src/services/auth.ts` implementing the `AuthManager` interface
    - `login(username, password, clientType)`: POST to `/api/auth/login` with `{ username, password, client_type: "tv" }`, store JWT via `react-native-keychain`
    - `logout()`: POST to `/api/auth/logout`, clear stored token
    - `getToken()`: read from keychain
    - `isTokenValid()`: decode JWT, check `exp` claim against current time (no network call)
    - `clearToken()`: remove from keychain
    - _Requirements: 1.2, 1.5, 1.6, 1.10, 1.11, 1.13_

  - [ ]* 5.3 Write property tests for AuthManager
    - **Property 2: Login stores token round-trip** — after login, getToken returns JWT with matching `sub` claim
    - **Validates: Requirements 1.2**
    - **Property 3: Sign-out clears token** — after logout, getToken returns null
    - **Validates: Requirements 1.5, 5.4**

  - [ ] 5.4 Create `tv-app/src/services/api.ts` implementing the `ApiClient` interface
    - axios instance with `baseURL: "https://mw.mzwcms.com/api"` and `timeout: 15000`
    - Request interceptor: inject `Authorization: Bearer <token>` from AuthManager
    - Response interceptor: on 401, call `AuthManager.clearToken()` and trigger navigation to LoginScreen
    - Methods: `getYears()`, `getMediaByYear(year, page, pageSize)`, `getMediaItemDetail(id, year)`
    - HTTPS only, no HTTP fallback
    - _Requirements: 1.7, 1.8, 1.9, 8.3_

  - [ ]* 5.5 Write property tests for ApiClient
    - **Property 4: 401 response clears token** — simulate 401, verify token cleared
    - **Validates: Requirements 1.7**
    - **Property 5: Bearer token injection on all authenticated requests** — verify Authorization header matches stored token
    - **Validates: Requirements 1.8**

- [ ] 6. Checkpoint — Verify services
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 7. Implement shared UI components
  - [ ] 7.1 Create `tv-app/src/components/LoadingSpinner.tsx`
    - Centered `ActivityIndicator` with "Loading..." text at 24sp
    - Uses theme COLORS and FONT_SIZE constants
    - _Requirements: 2.6_

  - [ ] 7.2 Create `tv-app/src/components/ErrorOverlay.tsx`
    - Props: `message: string`, `onRetry: () => void`
    - Centered error text at 24sp with focusable "Retry" `Pressable` button
    - Focus indicator: 3dp border, 1.05x scale
    - Minimum 48dp touch target on retry button
    - _Requirements: 8.1, 8.2, 8.4, 8.5_

  - [ ]* 7.3 Write property test for retry re-attempts
    - **Property 15: Retry re-attempts the failed request**
    - Generate random error scenarios, trigger retry via ErrorOverlay, verify same endpoint called again with loading state true during retry
    - **Validates: Requirements 8.5**

  - [ ] 7.4 Create `tv-app/src/components/ThumbnailCard.tsx`
    - Props: `item: MediaItemSummary`, `onSelect: () => void`
    - Display thumbnail image or placeholder with title text when `has_thumbnail` is false
    - Title text at 24sp below thumbnail
    - Focus indicator: 3dp border + 1.05x scale via `Pressable` focus state
    - Minimum 48dp × 48dp touch target
    - _Requirements: 2.5, 2.8, 6.5, 6.6_

  - [ ]* 7.5 Write property test for placeholder rendering
    - **Property 10: Placeholder rendered for missing thumbnails**
    - Generate `MediaItemSummary` with `has_thumbnail=false` or `thumbnail_url=null`, verify placeholder element rendered with title text
    - **Validates: Requirements 2.8**

  - [ ] 7.6 Create `tv-app/src/components/YearRow.tsx`
    - Props: `year: string`, `items: MediaItemSummary[]`, `loading: boolean`, `onEndReached: () => void`, `onSelectItem: (item: MediaItemSummary) => void`
    - Year label at 32sp using `formatYearLabel`
    - Horizontal FlatList of ThumbnailCard components
    - D-pad left/right focus movement within the row
    - Calls `onEndReached` when scrolled near end
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 3.3_

  - [ ] 7.7 Create `tv-app/src/components/TopBar.tsx`
    - Props: `onSignOut: () => void`
    - Left: app name text at 28sp
    - Right: "Sign Out" `Pressable` button, focusable via D-pad
    - _Requirements: 5.1, 5.2_

- [ ] 8. Implement LoginScreen
  - [ ] 8.1 Create `tv-app/src/screens/LoginScreen.tsx`
    - Two text inputs (username, password) and "Sign In" button, vertical layout
    - D-pad navigation top-to-bottom: username → password → sign in
    - On submit: call `AuthManager.login(username, password, "tv")`
    - On success: navigate to BrowseScreen
    - On 401: display "Invalid username or password. Please try again." at 24sp
    - No TopBar visible
    - All text uses sans-serif font, dark background, light text
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.13, 3.8, 3.9, 5.3, 6.1, 6.4_

  - [ ]* 8.2 Write property test for token-based launch routing
    - **Property 1: Token-based launch routing**
    - Generate random JWT payloads with exp in past/future/absent, verify routing decision: valid token → Browse, invalid/absent → Login
    - **Validates: Requirements 1.1, 1.10, 1.11**

  - [ ]* 8.3 Write unit tests for LoginScreen
    - Test invalid credentials shows error message (Req 1.4)
    - Test login request body includes `client_type: "tv"` (Req 1.13)
    - Test select on sign-in button submits credentials (Req 3.9)

- [ ] 9. Implement BrowseScreen
  - [ ] 9.1 Create `tv-app/src/screens/BrowseScreen.tsx`
    - TopBar at top with sign-out wired to AuthManager.logout
    - Vertical FlatList of YearRow components
    - Fetch year list from `/api/media/years` on mount
    - Lazy-load year media on row visibility via `onViewableItemsChanged`
    - Paginate horizontally: fetch next page when user scrolls near end of row
    - `"unknown_year"` displayed as "Unknown Year", rendered last
    - Loading spinner while fetching years
    - Error state with retry button if year fetch fails: "Could not load videos. Press OK to retry."
    - D-pad up/down moves focus between YearRows and TopBar
    - Back button prompts exit confirmation dialog
    - On thumbnail select: navigate to PlayerScreen with `{ itemId, year }`
    - _Requirements: 2.1, 2.2, 2.3, 2.6, 2.7, 3.3, 3.4, 3.5, 3.6, 5.3, 5.4_

  - [ ]* 9.2 Write property tests for BrowseScreen data
    - **Property 7: Year list renders correct count and order** — generate random year arrays, verify YearRow count matches and order preserved
    - **Validates: Requirements 2.1**
    - **Property 8: Pagination appends items without loss** — generate item arrays and page responses, verify concatenation preserves all items in order
    - **Validates: Requirements 2.2, 2.3**
    - **Property 9: Loading state active during fetches** — verify loading=true during fetch, false after resolve/reject
    - **Validates: Requirements 2.6**

  - [ ]* 9.3 Write unit tests for BrowseScreen
    - Test year list error shows "Could not load videos" with retry button (Req 2.7)
    - Test back button shows exit confirmation (Req 3.6)
    - Test TopBar visible on BrowseScreen (Req 5.3)

- [ ] 10. Implement PlayerScreen
  - [ ] 10.1 Create `tv-app/src/screens/PlayerScreen.tsx`
    - Full-screen `react-native-video` player
    - Fetch media detail from `/api/media/items/{id}?year={year}` on mount
    - Begin playback when valid `presigned_url` received
    - Overlay: video title at 28sp shown first 5 seconds and when controls visible
    - Transport controls: play/pause (select button), rewind 10s (left), forward 10s (right)
    - Back button stops playback, navigates to BrowseScreen
    - Playback completion auto-navigates to BrowseScreen
    - Buffering spinner overlay
    - Error state: "Video could not be loaded. Press OK to retry." with retry button that re-fetches media detail
    - No metadata panel, no transcript panel
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 4.6, 4.7, 4.8, 4.9, 3.5, 3.7_

  - [ ]* 10.2 Write property tests for PlayerScreen
    - **Property 11: Thumbnail selection fetches detail with correct parameters** — generate random id/year pairs, verify GET request URL matches `/api/media/items/{id}?year={year}`
    - **Validates: Requirements 3.5, 4.1**
    - **Property 12: Play/pause toggle is an involution** — generate random boolean states, verify toggle(toggle(state)) === state
    - **Validates: Requirements 4.4**

  - [ ]* 10.3 Write unit tests for PlayerScreen
    - Test back button navigates to BrowseScreen (Req 3.7)
    - Test PlayerScreen does not render metadata or transcript components (Req 4.6)
    - Test video load error shows "Video could not be loaded" with retry (Req 4.7)
    - Test playback completion navigates to BrowseScreen (Req 4.9)

- [ ] 11. Wire navigation and app entry point
  - [ ] 11.1 Create `tv-app/src/navigation/AppNavigator.tsx` with stack navigator
    - Define stack with 3 routes: Login, Browse, Player using `RootStackParamList`
    - On app launch: check token via `AuthManager.isTokenValid()`, route to Browse if valid, Login if not
    - _Requirements: 1.1, 1.10, 1.11, 6.3_

  - [ ] 11.2 Create `tv-app/App.tsx` entry point
    - Wrap AppNavigator in NavigationContainer
    - Apply global styles: dark background, sans-serif font family
    - _Requirements: 6.1, 6.4_

  - [ ]* 11.3 Write unit tests for navigation and wiring
    - Test navigation stack has exactly 3 routes (Req 6.3)
    - Test font family is sans-serif (Req 6.4)
    - Test API client baseURL is `https://mw.mzwcms.com/api` (Req 1.9)
    - Test API client timeout is 15000ms (Req 8.3)
    - Test TopBar not visible on LoginScreen or PlayerScreen (Req 5.3)
    - Test network error shows connection failure message (Req 8.1)
    - Test 503 error shows "service temporarily unavailable" message (Req 8.2)

- [ ] 12. Final checkpoint — Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Task 1 (backend change) is a cross-spec dependency and must be completed first
- Property tests use `fast-check` (TypeScript) for the TV app and `hypothesis` (Python) for the backend
- Each property test references its design property number and the requirements it validates
- Checkpoints ensure incremental validation at key milestones
