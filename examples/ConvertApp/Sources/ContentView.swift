import SwiftUI

struct ContentView: View {
    @EnvironmentObject var store: ConvertStore

    var body: some View {
        TabView {
            LengthView()
                .tabItem { Label("Length", systemImage: "ruler") }
            TemperatureView()
                .tabItem { Label("Temperature", systemImage: "thermometer.medium") }
        }
        .frame(minWidth: 420, minHeight: 300)
        .padding()
    }
}

struct LengthView: View {
    @EnvironmentObject var store: ConvertStore

    var body: some View {
        Form {
            TextField("Value", text: $store.lengthInput)
                .accessibilityIdentifier("lengthInput")
            Picker("From", selection: $store.lengthFrom) {
                ForEach(LengthUnit.allCases) { u in
                    Text(u.rawValue).tag(u)
                }
            }
            .accessibilityIdentifier("fromUnit")
            Picker("To", selection: $store.lengthTo) {
                ForEach(LengthUnit.allCases) { u in
                    Text(u.rawValue).tag(u)
                }
            }
            .accessibilityIdentifier("toUnit")
            Button("Swap") { store.swapLengthUnits() }
                .accessibilityIdentifier("swapUnits")
            LabeledContent("Result") {
                Text(store.lengthResult)
                    .accessibilityIdentifier("lengthResult")
            }
        }
        .padding()
    }
}

struct TemperatureView: View {
    @EnvironmentObject var store: ConvertStore

    var body: some View {
        Form {
            TextField("Value", text: $store.tempInput)
                .accessibilityIdentifier("tempInput")
            Picker("From", selection: $store.tempFrom) {
                ForEach(TempUnit.allCases) { u in
                    Text(u.rawValue).tag(u)
                }
            }
            .pickerStyle(.segmented)
            .accessibilityIdentifier("tempFrom")
            Picker("To", selection: $store.tempTo) {
                ForEach(TempUnit.allCases) { u in
                    Text(u.rawValue).tag(u)
                }
            }
            .pickerStyle(.segmented)
            .accessibilityIdentifier("tempTo")
            LabeledContent("Result") {
                Text(store.tempResult)
                    .accessibilityIdentifier("tempResult")
            }
        }
        .padding()
    }
}
