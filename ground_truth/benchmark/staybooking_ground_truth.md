# StayBooking Ground Truth Snapshot

## Source Repositories
- Backend: `https://github.com/hjguo48/staybooking-project.git` @ `81b85eab7d2d14076eb9b32234522b2f42c66382`
- Frontend: `https://github.com/hjguo48/stayboookingfe.git` @ `4a7a9551a37d6210c40760b30218b20cb03f8394`

## Counts
- Backend endpoints: 10
- Backend entities: 3
- Backend controllers/services/repositories: 3/5/3
- Frontend components: 4
- Frontend API calls: 10

## Backend Endpoints
- `POST /auth/register` (AuthenticationController.register)
- `POST /auth/login` (AuthenticationController.login)
- `GET /bookings` (BookingController.getGuestBookings)
- `POST /bookings` (BookingController.createBooking)
- `DELETE /bookings/{bookingId}` (BookingController.deleteBooking)
- `GET /listings` (ListingController.getListings)
- `POST /listings` (ListingController.createListing)
- `DELETE /listings/{listingId}` (ListingController.deleteListing)
- `GET /listings/search` (ListingController.search)
- `GET /listings/{listingId}/bookings` (ListingController.getListingBookings)

## Backend Entities
- `BookingEntity` table=bookings id=['id']
- `ListingEntity` table=listings id=['id']
- `UserEntity` table=users id=['id']

## Frontend API Calls
- `POST /auth/login` via `login`
- `POST /auth/register` via `register`
- `GET /bookings` via `getReservations`
- `GET /listings` via `getStaysByHost`
- `GET /listings/search` via `searchStays`
- `DELETE /listings/${stayId}` via `deleteStay`
- `POST /bookings` via `bookStay`
- `DELETE /bookings/${reservationId}` via `cancelReservation`
- `GET /listings/${stayId}/bookings` via `getReservationsByStay`
- `POST /listings` via `uploadStay`
