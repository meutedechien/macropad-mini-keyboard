// snap <nb_images> <intervalle_s> <dossier> [nom_caméra]
// Prend une série de photos JPEG avec la webcam (pour observer les LED du macropad).
import AVFoundation
import CoreImage
import AppKit

let args = CommandLine.arguments
let count = args.count > 1 ? Int(args[1])! : 1
let interval = args.count > 2 ? Double(args[2])! : 0.5
let outDir = args.count > 3 ? args[3] : "."
let camName = args.count > 4 ? args[4] : "FaceTime"

final class Grabber: NSObject, AVCaptureVideoDataOutputSampleBufferDelegate {
    let ctx = CIContext()
    var last = Date.distantPast
    var taken = 0
    var warmup = 15
    func captureOutput(_ o: AVCaptureOutput, didOutput sb: CMSampleBuffer, from c: AVCaptureConnection) {
        if warmup > 0 { warmup -= 1; return }  // laisse l'exposition se stabiliser
        guard Date().timeIntervalSince(last) >= interval, let px = CMSampleBufferGetImageBuffer(sb) else { return }
        last = Date()
        let img = CIImage(cvPixelBuffer: px)
        let path = String(format: "%@/f%03d.jpg", outDir, taken)
        try? ctx.writeJPEGRepresentation(of: img, to: URL(fileURLWithPath: path),
                                         colorSpace: CGColorSpaceCreateDeviceRGB(),
                                         options: [kCGImageDestinationLossyCompressionQuality as CIImageRepresentationOption: 0.6])
        print(path); fflush(stdout)
        taken += 1
        if taken >= count { exit(0) }
    }
}

let sem = DispatchSemaphore(value: 0)
AVCaptureDevice.requestAccess(for: .video) { ok in
    if !ok { fputs("Accès caméra refusé\n", stderr); exit(1) }
    sem.signal()
}
sem.wait()

let devices = AVCaptureDevice.DiscoverySession(deviceTypes: [.builtInWideAngleCamera, .external, .continuityCamera],
                                               mediaType: .video, position: .unspecified).devices
guard let dev = devices.first(where: { $0.localizedName.contains(camName) }) ?? devices.first else {
    fputs("Aucune caméra\n", stderr); exit(1)
}
let session = AVCaptureSession()
session.sessionPreset = .medium
session.addInput(try! AVCaptureDeviceInput(device: dev))
let out = AVCaptureVideoDataOutput()
let g = Grabber()
out.setSampleBufferDelegate(g, queue: DispatchQueue(label: "cam"))
session.addOutput(out)
session.startRunning()
DispatchQueue.main.asyncAfter(deadline: .now() + 60) { fputs("Délai dépassé\n", stderr); exit(2) }
RunLoop.main.run()
