/** @odoo-module **/
import { Component, onMounted, useRef, xml } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { standardFieldProps } from "@web/views/fields/standard_field_props";

export class GeoPickerField extends Component {
    static template = xml/* xml */`
        <div class="o_geo_picker">
            <div t-ref="map" style="height:280px;"></div>
            <div class="mt-2 small text-muted">
                <span>Lat: <t t-esc="state.lat"/></span>
                <span class="ms-3">Lng: <t t-esc="state.lng"/></span>
            </div>
        </div>
    `;
    static props = { ...standardFieldProps };
    static supportedTypes = ["float", "char", "json"];
    setup() {
        this.mapRef = useRef("map");
        this.state = { lat: 0, lng: 0 };
        onMounted(() => this._initMap());
    }
    _getInitCoords() {
        const rec = this.props.record?.data || {};
        const lat = Number(rec.geo_lat ?? 41.311081);
        const lng = Number(rec.geo_lng ?? 69.240562);
        this.state.lat = lat;
        this.state.lng = lng;
        return [lat, lng];
    }
    async _save(lat, lng) {
        this.state.lat = lat;
        this.state.lng = lng;
        await this.props.update({ geo_lat: lat, geo_lng: lng });
    }
    _initMap() {
        const L = window.L;
        if (!L) return;
        const [lat, lng] = this._getInitCoords();
        const map = L.map(this.mapRef.el).setView([lat, lng], 13);
        L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
            maxZoom: 19,
        }).addTo(map);
        const marker = L.marker([lat, lng], { draggable: !this.props.readonly }).addTo(map);
        const saveFrom = (ll) => this._save(ll.lat, ll.lng);
        map.on("click", (e) => { marker.setLatLng(e.latlng); saveFrom(e.latlng); });
        marker.on("dragend", (e) => saveFrom(e.target.getLatLng()));
        this._map = map;
        this._marker = marker;
    }
}

registry.category("fields").add("geo_picker", GeoPickerField);
