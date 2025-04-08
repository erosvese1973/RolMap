/**
 * Map related utility functions
 */

/**
 * Calculates the center point of multiple coordinates
 * @param {Array} coordinates - Array of coordinates [lng, lat]
 * @returns {Object} The center point {lat, lng}
 */
function calculateCenter(coordinates) {
    if (!coordinates || coordinates.length === 0) {
        // Default to center of Italy if no coordinates
        return {lat: 41.9, lng: 12.5};
    }
    
    let totalLat = 0;
    let totalLng = 0;
    
    coordinates.forEach(coord => {
        totalLng += coord[0];
        totalLat += coord[1];
    });
    
    return {
        lat: totalLat / coordinates.length,
        lng: totalLng / coordinates.length
    };
}

/**
 * Styles the GeoJSON features on the map
 * @param {google.maps.Data} mapData - The map data object
 * @param {string} fillColor - The fill color to use
 * @param {number} fillOpacity - The fill opacity (0-1)
 */
function styleGeoJsonFeatures(mapData, fillColor = '#FF9800', fillOpacity = 0.5) {
    mapData.setStyle({
        fillColor: fillColor,
        fillOpacity: fillOpacity,
        strokeColor: '#FF5722',
        strokeWeight: 2,
        strokeOpacity: 1
    });
}

/**
 * Adds an info window to GeoJSON features
 * @param {google.maps.Map} map - The Google Maps instance
 * @param {google.maps.Data} mapData - The map data object
 * @param {string} agentName - The name of the agent to display
 */
function addInfoWindowToFeatures(map, mapData, agentName) {
    let infoWindow = new google.maps.InfoWindow();
    
    mapData.addListener('click', function(event) {
        const properties = event.feature.getProperty('properties') || {};
        const id = properties.id || 'N/A';
        const name = properties.name || 'Comune';
        
        infoWindow.setContent(`
            <div style="padding: 10px;">
                <h6>${name}</h6>
                <p style="margin-bottom: 5px;"><strong>Codice:</strong> ${id}</p>
                <p style="margin-bottom: 0;"><strong>Agente:</strong> ${agentName}</p>
            </div>
        `);
        
        infoWindow.setPosition(event.latLng);
        infoWindow.open(map);
    });
}

/**
 * Adds a legend to the map
 * @param {google.maps.Map} map - The Google Maps instance
 * @param {string} agentName - The name of the agent
 * @param {number} count - The number of municipalities
 */
function addMapLegend(map, agentName, count) {
    const legend = document.createElement('div');
    legend.style.backgroundColor = 'rgba(0, 0, 0, 0.7)';
    legend.style.borderRadius = '5px';
    legend.style.boxShadow = '0 2px 6px rgba(0, 0, 0, .3)';
    legend.style.color = 'white';
    legend.style.fontSize = '14px';
    legend.style.margin = '10px';
    legend.style.padding = '15px';
    
    legend.innerHTML = `
        <h6 style="margin-top: 0; margin-bottom: 5px; font-weight: bold;">${agentName}</h6>
        <div style="display: flex; align-items: center; margin-bottom: 5px;">
            <div style="width: 20px; height: 20px; background-color: #FF9800; margin-right: 10px;"></div>
            <span>${count} comuni assegnati</span>
        </div>
    `;
    
    // Add the legend to the map
    map.controls[google.maps.ControlPosition.LEFT_BOTTOM].push(legend);
}
