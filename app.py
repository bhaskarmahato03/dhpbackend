from flask import Flask, jsonify,request , send_from_directory # Removed render_template, send_file
import pandas as pd
from flask_cors import CORS
import os
# import json # Not explicitly used, pandas handles JSON conversion
# import os # Not needed if not creating directories or saving files server-side
# import seaborn as sns # Not needed if plots are generated client-side
# import matplotlib.pyplot as plt # Not needed if plots are generated client-side

app = Flask(__name__)
CORS(app)  # Enable CORS for all routes
# ✅ Load data at global scope - This is good for performance
try:
    data = pd.read_csv("hospital_data.csv")
except FileNotFoundError:
    print("Error: 'hospital_data.csv' not found. Please ensure the file is in the correct directory.")
    # You might want to exit or provide default empty data if the file is critical
    data = pd.DataFrame() # Create an empty DataFrame as a fallback


# ❌ Removed: os.makedirs("static/images", exist_ok=True) - No longer saving images server-side by default

# ❌ Removed: def load_hospital_data(): - We will use the global 'data' DataFrame directly

@app.route('/')
def home_api():
    """
    Basic API information or health check.
    """
    return jsonify({
        "message": "Welcome to the Hospital Data API",
        "status": "healthy",
        "documentation_url": "/api/docs" # Placeholder for potential future docs
    })

@app.route('/api/stats') # Changed from /stats
def stats_api():
    """
    Provides overall statistics from the hospital data.
    """
    if data.empty:
        return jsonify({"error": "Data not loaded or empty"}), 500
    # Convert all data to JSON for JavaScript
    stats_data = data.to_dict(orient='records')
    return jsonify(stats_data)

@app.route('/api/map-data') # Changed from /map
def map_view_api():
    """
    Provides data formatted for map display, including hospital details per state and a list of states.
    """
    if data.empty:
        return jsonify({"error": "Data not loaded or empty"}), 500

    hospital_data_processed = []
    for index, row in data.iterrows():
        try:
            hospital_data_processed.append({
                'state': row['State/UT/Division'],
                'total_hospitals': int(row['Number of Total Hospitals (Govt.)']) if pd.notna(row['Number of Total Hospitals (Govt.)']) else 0,
                'rural_hospital_beds': int(row['Number of beds in Rural Hospitals (Govt.)']) if pd.notna(row['Number of beds in Rural Hospitals (Govt.)']) else 0, # Corrected key name for clarity
                'urban_hospitals': int(row['Number of Urban Hospitals (Govt.)']) if pd.notna(row['Number of Urban Hospitals (Govt.)']) else 0,
                'avg_population_served_per_hospital': float(row['Average Population Served Per Govt. Hospital']) if pd.notna(row['Average Population Served Per Govt. Hospital']) else 0, # Corrected key name
                'Average Population Served Per Govt. Hospital Bed': float(row["Average Population Served Per Govt. Hospital Bed"]) if pd.notna(row["Average Population Served Per Govt. Hospital Bed"]) else None
            })
        except KeyError as e:
            return jsonify({"error": f"Missing expected column in CSV: {e}"}), 500
        except ValueError as e:
            return jsonify({"error": f"Data conversion error for row {index}: {e}"}), 500


    states = sorted(data['State/UT/Division'].unique().tolist())

    return jsonify({
        'hospital_data': hospital_data_processed,
        'states': states
    })

@app.route('/api/hospital-data') # This was already an API route
def get_hospital_data():
    """
    Returns the raw hospital data in JSON format.
    """
    if data.empty:
        return jsonify({"error": "Data not loaded or empty"}), 500
    return jsonify(data.to_dict(orient='records'))


@app.route('/api/analysis-summary') # Changed from /analysis
def analysis_api():
    """
    Provides aggregated data for various analyses (charts) to be rendered by the frontend.
    """
    if data.empty:
        return jsonify({"error": "Data not loaded or empty"}), 500

    try:
        # --- Data for Line Chart: Rural and Urban Hospitals per State ---
        rural_hospitals_series = data.groupby("State/UT/Division")["Number of Rural Hospitals (Govt.)"].sum()
        urban_hospitals_series = data.groupby("State/UT/Division")["Number of Urban Hospitals (Govt.)"].sum()
        line_chart_states = rural_hospitals_series.index.tolist()
        line_chart_data = {
            "states": line_chart_states,
            "rural_hospitals": rural_hospitals_series.values.tolist(),
            "urban_hospitals": urban_hospitals_series.reindex(line_chart_states, fill_value=0).values.tolist() # Ensure alignment
        }

        # --- Data for Bar Chart: Estimated ICU Beds per State ---
        icu_beds_series = data.groupby("State/UT/Division")["Estimated total ICU beds"].sum()
        bar_chart_states = icu_beds_series.index.tolist()
        icu_bar_chart_data = {
            "states": bar_chart_states,
            "icu_beds": icu_beds_series.values.tolist()
        }

        # --- Data for Scatter Plot: Estimated Ventilators per State ---
        public_ventilators_series = data.groupby("State/UT/Division")["Estimated ventilators in public sector"].sum()
        private_ventilators_series = data.groupby("State/UT/Division")["Estimated ventilators in private sector"].sum()
        scatter_plot_states = public_ventilators_series.index.tolist() # Assuming states are same for public and private
        ventilator_scatter_data = {
            "states": scatter_plot_states,
            "public_ventilators": public_ventilators_series.values.tolist(),
            "private_ventilators": private_ventilators_series.reindex(scatter_plot_states, fill_value=0).values.tolist() # Ensure alignment
        }

        # Get unique sorted states for dropdowns or general use
        all_states = sorted(data["State/UT/Division"].unique().tolist())

        return jsonify({
            "line_chart_data": line_chart_data,
            "icu_bar_chart_data": icu_bar_chart_data,
            "ventilator_scatter_data": ventilator_scatter_data,
            "all_states": all_states
        })
    except KeyError as e:
        return jsonify({"error": f"Missing expected column for analysis: {e}"}), 500
    except Exception as e:
        return jsonify({"error": f"An error occurred during analysis: {str(e)}"}), 500


@app.route('/api/pie-data/<state>') # Changed from /get_pie_data/<state> for consistency
def get_pie_data_api(state):
    """
    Provides data for generating pie charts for a specific state (hospitals and beds).
    """
    if data.empty:
        return jsonify({"error": "Data not loaded or empty"}), 500
        
    filtered_data = data[data["State/UT/Division"] == state]
    if filtered_data.empty:
        return jsonify({"error": "State not found"}), 404
    
    try:
        # Ensure we take the first row if multiple exist for a state (shouldn't if data is clean)
        state_row = filtered_data.iloc[0]

        rural_hospitals = int(state_row["Number of Rural Hospitals (Govt.)"] or 0)
        urban_hospitals = int(state_row["Number of Urban Hospitals (Govt.)"] or 0)
        
        rural_beds = int(state_row["Number of beds in Rural Hospitals (Govt.)"] or 0)
        urban_beds = int(state_row["Number of beds in Urban Hospitals (Govt.)"] or 0)

        return jsonify({
            "state": state,
            "hospitals": {"rural": rural_hospitals, "urban": urban_hospitals},
            "beds": {"rural": rural_beds, "urban": urban_beds}
        })
    except KeyError as e:
        return jsonify({"error": f"Missing expected column for state {state}: {e}"}), 500
    except Exception as e:
        return jsonify({"error": f"An error occurred processing data for state {state}: {str(e)}"}), 500

@app.route('/api/icu-data/<state>') # Changed from /get_icu_data/<state> for consistency
def get_icu_data_api(state):
    """
    Provides ICU and ventilator data for a specific state.
    """
    if data.empty:
        return jsonify({"error": "Data not loaded or empty"}), 500

    filtered_data = data[data["State/UT/Division"] == state]
    if filtered_data.empty:
        return jsonify({"error": "State not found"}), 404
    
    try:
        state_row = filtered_data.iloc[0]
        
        public_icu = int(state_row["Estimated ICU beds in public sector"] or 0)
        private_icu = int(state_row["Estimated ICU beds in private sector"] or 0)

        public_ventilators = int(state_row["Estimated ventilators in public sector"] or 0) # Renamed for clarity
        private_ventilators = int(state_row["Estimated ventilators in private sector"] or 0) # Renamed for clarity

        return jsonify({
            "state": state,
            "icu_beds": {"public": public_icu, "private": private_icu}, # Renamed for clarity
            "ventilators": {"public": public_ventilators, "private": private_ventilators} # Renamed for clarity
        })
    except KeyError as e:
        return jsonify({"error": f"Missing expected column for state {state}: {e}"}), 500
    except Exception as e:
        return jsonify({"error": f"An error occurred processing ICU data for state {state}: {str(e)}"}), 500


if __name__ == '__main__':
    # For production, use a WSGI server like Gunicorn or Waitress
    app.run(debug=True)