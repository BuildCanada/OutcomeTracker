import { Appsignal } from "@appsignal/nodejs";

new Appsignal({
  active: true,
  name: "OutcomesTracker",
  disableDefaultInstrumentations: [
    // Add the following line inside the list
    "@opentelemetry/instrumentation-http",
  ],
});
