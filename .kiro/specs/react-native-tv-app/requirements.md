# Requirements Document

## Introduction

A React Native TV application that provides a simplified, D-pad-optimized video browsing and playback experience for older adults. The app connects to the existing FastAPI backend (deployed at `https://mw.mzwcms.com`) using the same JWT authentication and media API endpoints as the React web frontend. It targets Android TV, Amazon Fire TV, and Apple TV. The app deliberately omits metadata and transcript panels present in the web frontend, focusing exclusively on browse-by-year and full-screen video playback.

## Glossary

- **TV_App**: The React Native TV application targeting Android TV, Fire TV, and Apple TV
- **Backend_API**: The existing FastAPI server deployed at `https://mw.mzwcms.com/api`
- **Auth_Service**: The authentication subsystem of Backend_API handling JWT token issuance and validation
- **Media_Service**: The media subsystem of Backend_API providing year listings, paginated media items, and presigned video URLs
- **API_Client**: The HTTP client module within TV_App responsible for all Backend_API communication
- **Auth_Manager**: The module within TV_App responsible for login, logout, token storage, and token injection into API requests
- **Login_Screen**: The screen displayed to unauthenticated users for credential entry
- **Browse_Screen**: The main screen displaying year-labeled rows of horizontally scrollable video thumbnails
- **Player_Screen**: The full-screen video playback screen with standard TV transport controls
- **Focus_Engine**: The subsystem within TV_App that manages D-pad navigation focus state across all screens
- **Year_Row**: A single horizontal scrollable row of video thumbnails labeled by year on the Browse_Screen
- **Top_Bar**: The persistent header bar displaying the app name/logo and sign-in/sign-out button
- **D-pad**: The directional pad remote control input (up, down, left, right, select, back) used on all target TV platforms
- **Presigned_URL**: A time-limited S3 URL returned by Backend_API for secure video streaming

## Requirements

### Requirement 1: Authentication

**User Story:** As a family member, I want to sign in with my existing credentials on the TV, so that I can access the family media library without creating a separate account.

#### Acceptance Criteria

1. WHEN the TV_App launches and no valid JWT token exists in secure storage, THE TV_App SHALL navigate to the Login_Screen
2. WHEN the user submits valid credentials on the Login_Screen, THE Auth_Manager SHALL send a POST request to `Backend_API /api/auth/login` with `{username, password}` and store the returned JWT token in platform-secure storage
3. WHEN the Auth_Manager receives a valid JWT token from Auth_Service, THE TV_App SHALL navigate to the Browse_Screen
4. IF Auth_Service returns a 401 response to a login attempt, THEN THE Login_Screen SHALL display the message "Invalid username or password. Please try again." with a minimum text size of 24sp
5. WHEN the user selects the sign-out button on the Top_Bar, THE Auth_Manager SHALL send a POST request to `Backend_API /api/auth/logout`, clear the stored JWT token, and navigate to the Login_Screen
6. THE Auth_Manager SHALL store JWT tokens using platform-secure storage (Android Keystore on Android TV/Fire TV, Keychain on Apple TV) and SHALL NOT store tokens in plaintext AsyncStorage or local files
7. WHEN the API_Client receives a 401 response from any Backend_API endpoint, THE Auth_Manager SHALL clear the stored token and THE TV_App SHALL navigate to the Login_Screen
8. THE API_Client SHALL include the JWT token as a Bearer token in the Authorization header of every authenticated request to Backend_API
9. THE API_Client SHALL use `https://mw.mzwcms.com/api` as the base URL for all Backend_API requests and SHALL NOT permit HTTP (non-TLS) connections
10. WHEN the TV_App launches and a JWT token exists in secure storage, THE Auth_Manager SHALL check the token's `exp` claim; IF the token is not expired, THE TV_App SHALL navigate directly to the Browse_Screen without requiring re-authentication
11. IF the stored JWT token is expired at app launch, THE Auth_Manager SHALL clear the token and THE TV_App SHALL navigate to the Login_Screen
12. THE Backend_API login endpoint SHALL accept an optional `client_type` field in the login request body; WHEN `client_type` is `"tv"`, THE Auth_Service SHALL issue a JWT token with a 30-day expiry instead of the default 24-hour expiry
13. THE TV_App login request SHALL include `client_type: "tv"` in the POST body to `Backend_API /api/auth/login`

### Requirement 2: Browse Screen — Year Rows

**User Story:** As a family member, I want to browse family videos organized by year in horizontal rows, so that I can find videos from a specific time period without complex navigation.

#### Acceptance Criteria

1. WHEN the Browse_Screen loads, THE Media_Service client SHALL fetch the year list from `Backend_API GET /api/media/years` and render one Year_Row per returned year in the order provided by the API (numeric years reverse chronological, `unknown_year` last displayed as "Unknown Year")
2. WHEN a Year_Row becomes visible on screen, THE Media_Service client SHALL fetch the first page of media items from `Backend_API GET /api/media/years/{year}?page=1&page_size=20` and display thumbnails horizontally within that Year_Row
3. WHEN the user scrolls horizontally to the end of a Year_Row that has a non-null `next_page` value, THE Media_Service client SHALL fetch the next page and append the new thumbnails to that Year_Row
4. THE Browse_Screen SHALL display each Year_Row label (the year value) in a minimum text size of 32sp with a color contrast ratio of at least 4.5:1 against the background
5. THE Browse_Screen SHALL display each thumbnail title in a minimum text size of 24sp with a color contrast ratio of at least 4.5:1 against the background
6. WHILE the Media_Service client is fetching year data or media items, THE Browse_Screen SHALL display a visible loading indicator (spinner or "Loading..." text at minimum 24sp)
7. IF the Backend_API returns an error for the year list request, THEN THE Browse_Screen SHALL display the message "Could not load videos. Press OK to retry." with a focusable retry button
8. THE Browse_Screen SHALL display items without thumbnails using a placeholder image that includes the item title text

### Requirement 3: D-pad Navigation and Focus Management

**User Story:** As an older adult using a TV remote, I want all navigation to work with the D-pad directional buttons, so that I do not need to learn complex gestures or use a touchscreen.

#### Acceptance Criteria

1. THE Focus_Engine SHALL ensure exactly one UI element is focused at all times on every screen
2. THE Focus_Engine SHALL render a visible focus indicator (highlight ring or border) around the currently focused element with a minimum border width of 3dp and a color contrast ratio of at least 3:1 against adjacent colors
3. WHEN the user presses the D-pad left or right within a Year_Row, THE Focus_Engine SHALL move focus to the adjacent thumbnail in that row
4. WHEN the user presses the D-pad up or down on the Browse_Screen, THE Focus_Engine SHALL move focus to the nearest focusable element in the adjacent Year_Row or the Top_Bar
5. WHEN the user presses the D-pad select button on a focused thumbnail, THE TV_App SHALL navigate to the Player_Screen for that media item
6. WHEN the user presses the D-pad back button on the Browse_Screen, THE TV_App SHALL prompt the user to confirm exit rather than immediately closing the app
7. WHEN the user presses the D-pad back button on the Player_Screen, THE TV_App SHALL stop video playback and navigate back to the Browse_Screen
8. THE Login_Screen SHALL support D-pad navigation between the username field, password field, and sign-in button in a top-to-bottom order
9. WHEN the user presses the D-pad select button on the Login_Screen sign-in button, THE Login_Screen SHALL submit the credentials

### Requirement 4: Video Playback

**User Story:** As a family member, I want to watch family videos in full screen with simple play/pause and seek controls, so that I can enjoy the content without distractions.

#### Acceptance Criteria

1. WHEN the user selects a thumbnail on the Browse_Screen, THE TV_App SHALL fetch the media item detail from `Backend_API GET /api/media/items/{id}?year={year}` and navigate to the Player_Screen
2. WHEN the Player_Screen receives a valid `presigned_url` from the media item detail response, THE Player_Screen SHALL begin video playback in full-screen mode
3. THE Player_Screen SHALL provide play/pause, rewind (10-second skip back), and fast-forward (10-second skip forward) controls accessible via D-pad
4. WHEN the user presses the D-pad select button during playback, THE Player_Screen SHALL toggle between play and pause states
5. THE Player_Screen SHALL display the video title in a minimum text size of 28sp overlaid on the video during the first 5 seconds of playback and when transport controls are visible
6. THE Player_Screen SHALL NOT display metadata panels or transcript panels
7. IF the presigned_url has expired or the video fails to load, THEN THE Player_Screen SHALL display the message "Video could not be loaded. Press OK to retry." with a focusable retry button that re-fetches the media item detail
8. WHILE the video is buffering, THE Player_Screen SHALL display a visible loading spinner centered on the screen
9. WHEN the video playback reaches the end, THE Player_Screen SHALL automatically navigate back to the Browse_Screen

### Requirement 5: Top Bar

**User Story:** As a family member, I want to see the app name and a sign-out option at the top of the screen, so that I always know where I am and can sign out when needed.

#### Acceptance Criteria

1. THE Top_Bar SHALL display the app name or logo on the left side with a minimum text size of 28sp
2. WHILE the user is authenticated, THE Top_Bar SHALL display a "Sign Out" button on the right side that is focusable via D-pad
3. THE Top_Bar SHALL be visible on the Browse_Screen and SHALL NOT be visible on the Login_Screen or Player_Screen
4. WHEN the Top_Bar "Sign Out" button receives D-pad select, THE Auth_Manager SHALL execute the sign-out flow as defined in Requirement 1.5

### Requirement 6: Visual Design for Older Adults

**User Story:** As an older adult, I want the TV app to use large text, high contrast, and simple layouts, so that I can read and navigate the interface comfortably from my couch.

#### Acceptance Criteria

1. THE TV_App SHALL use a dark background color (luminance ≤ 20% of maximum) with light foreground text (luminance ≥ 80% of maximum) as the default color scheme
2. THE TV_App SHALL use a minimum text size of 24sp for all body text, 28sp for section headers, and 32sp for screen titles
3. THE TV_App SHALL limit navigation depth to a maximum of three screens: Login_Screen → Browse_Screen → Player_Screen
4. THE TV_App SHALL use sans-serif font families for all text elements
5. THE TV_App SHALL provide a minimum touch/focus target size of 48dp × 48dp for all interactive elements
6. WHILE any interactive element has D-pad focus, THE TV_App SHALL scale that element by a minimum factor of 1.05 or apply a visible highlight border of at least 3dp width

### Requirement 7: Platform Compatibility

**User Story:** As a family member with a Fire TV Stick, Android TV, or Apple TV, I want the app to work on my specific device, so that I do not need to buy new hardware.

#### Acceptance Criteria

1. THE TV_App SHALL build and run on Android TV devices running Android API level 21 (Lollipop) or higher
2. THE TV_App SHALL build and run on Amazon Fire TV devices (Fire OS 5 or higher)
3. THE TV_App SHALL build and run on Apple TV devices running tvOS 15.0 or higher
4. THE TV_App SHALL use `react-native-tvos` for Apple TV support and standard React Native with Android TV extensions for Android TV and Fire TV
5. THE TV_App codebase SHALL share TypeScript type definitions compatible with the existing web frontend type definitions in `frontend/src/types/media.ts`

### Requirement 8: Network Error Handling

**User Story:** As a family member with a potentially unreliable home network, I want clear error messages and retry options when something goes wrong, so that I am not confused by technical failures.

#### Acceptance Criteria

1. IF the API_Client cannot reach Backend_API due to a network timeout or connection failure, THEN THE TV_App SHALL display the message "Could not connect to the server. Check your internet connection and press OK to retry." with a focusable retry button
2. IF the API_Client receives a 503 response from Backend_API, THEN THE TV_App SHALL display the message "The service is temporarily unavailable. Press OK to try again." with a focusable retry button
3. THE API_Client SHALL use a request timeout of 15 seconds for all Backend_API requests
4. THE TV_App SHALL display all error messages in a minimum text size of 24sp with a color contrast ratio of at least 4.5:1 against the background
5. WHEN the user activates a retry button, THE TV_App SHALL re-attempt the failed request and display a loading indicator during the retry
