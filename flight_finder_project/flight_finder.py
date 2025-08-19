from flask import Flask, request, render_template
from amadeus import Client, ResponseError
from dotenv import load_dotenv
import os
from datetime import datetime

# Load environment variables
load_dotenv()

# Get API credentials
client_id = os.getenv("AMADEUS_CLIENT_ID")
client_secret = os.getenv("AMADEUS_CLIENT_SECRET")

# Initialize Amadeus client
amadeus = Client(client_id=client_id, client_secret=client_secret)

app = Flask(__name__)


def format_flight_data(data):
    """Convert Amadeus raw JSON into a simpler structure for templates."""
    results = []
    for offer in data:
        price = offer["price"]["total"]
        segments = []
        for itinerary in offer.get("itineraries", []):
            for segment in itinerary.get("segments", []):
                segments.append({
                    "from": segment["departure"]["iataCode"],
                    "departure": format_datetime(segment["departure"]["at"]),
                    "to": segment["arrival"]["iataCode"],
                    "arrival": format_datetime(segment["arrival"]["at"]),
                    "airline": segment["carrierCode"],
                    "number": segment["number"]
                })
        results.append({"price": price, "segments": segments})
    return results


def format_datetime(dt_str):
    """Convert API datetime string into readable format."""
    try:
        dt = datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
        return dt.strftime("%b %d, %Y %H:%M")
    except Exception:
        return dt_str


def validate_iata(code):
    """Ensure IATA code is exactly 3 letters."""
    return len(code) == 3 and code.isalpha()


@app.route("/", methods=["GET", "POST"])
def search_flights():
    if request.method == "POST":
        origin = request.form.get("origin", "").strip().upper()
        destination = request.form.get("destination", "").strip().upper()
        departure_date = request.form.get("departure_date", "").strip()
        return_date = request.form.get("return_date", "").strip()

        # Validate input
        if not (validate_iata(origin) and validate_iata(destination)):
            return render_template("index.html", error="Invalid IATA codes.")

        if not departure_date:
            return render_template("index.html", error="Please select a departure date.")

        if return_date and return_date < departure_date:
            return render_template("index.html", error="Return date cannot be before departure date.")

        try:
            # Search outbound flights
            response = amadeus.shopping.flight_offers_search.get(
                originLocationCode=origin,
                destinationLocationCode=destination,
                departureDate=departure_date,
                adults=1,
                max=5
            )
            outbound_flights = format_flight_data(response.data)

            # Search return flights if applicable
            return_flights = []
            if return_date:
                response_return = amadeus.shopping.flight_offers_search.get(
                    originLocationCode=destination,
                    destinationLocationCode=origin,
                    departureDate=return_date,
                    adults=1,
                    max=5
                )
                return_flights = format_flight_data(response_return.data)

            if not outbound_flights:
                return render_template("index.html", error="No flights found. Try different dates or locations.")

            return render_template(
                "results.html",
                outbound=outbound_flights,
                return_flights=return_flights
            )

        except ResponseError as e:
            return render_template("index.html", error=f"API error: {str(e)}")

    return render_template("index.html", error=None)


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))