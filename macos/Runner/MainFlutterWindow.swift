import Cocoa
import CFNetwork
import FlutterMacOS

class MainFlutterWindow: NSWindow {
  private var deviceChannel: FlutterMethodChannel?

  override func awakeFromNib() {
    let flutterViewController = FlutterViewController()
    let windowFrame = self.frame
    self.contentViewController = flutterViewController
    self.setFrame(windowFrame, display: true)

    RegisterGeneratedPlugins(registry: flutterViewController)

    title = Bundle.main.object(forInfoDictionaryKey: "CFBundleDisplayName") as? String ?? "红果鉴"
    setContentSize(NSSize(width: 1100, height: 760))
    contentMinSize = NSSize(width: 720, height: 540)
    center()

    let channel = FlutterMethodChannel(
      name: "duanju/device",
      binaryMessenger: flutterViewController.engine.binaryMessenger
    )
    deviceChannel = channel
    channel.setMethodCallHandler { call, result in
      guard call.method == "systemProxy" else {
        result(FlutterMethodNotImplemented)
        return
      }
      let settings = CFNetworkCopySystemProxySettings()?.takeRetainedValue() as? [String: Any] ?? [:]
      func address(_ prefix: String) -> String {
        guard (settings["\(prefix)Enable"] as? NSNumber)?.boolValue == true,
              let host = settings["\(prefix)Proxy"] as? String,
              let port = settings["\(prefix)Port"] as? NSNumber,
              !host.isEmpty, port.intValue > 0 else { return "" }
        let name = host.contains(":") ? "[\(host)]" : host
        return "http://\(name):\(port.intValue)"
      }
      let http = address("HTTP")
      let https = address("HTTPS")
      result([
        "http": http,
        "https": https.isEmpty ? http : https,
        "bypass": settings["ExceptionsList"] as? [String] ?? [],
        "pac": (settings["ProxyAutoConfigEnable"] as? NSNumber)?.boolValue == true,
      ])
    }

    super.awakeFromNib()
  }
}
