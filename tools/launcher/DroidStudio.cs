// Windows starter for Droid Studio, compiled by tools/build_portable.py with the
// C# compiler that ships with the .NET Framework (no extra tools needed).
//
// Without an embedded payload it sits next to runtime\ in the portable folder
// and starts the app. With an embedded payload (the single-file Droid-Studio.exe)
// it first unpacks the app into a "Droid Studio" folder next to itself; later
// starts reuse that folder. Case data (data\, Sicherungen\) is never touched.
using System;
using System.Diagnostics;
using System.IO;
using System.IO.Compression;
using System.Reflection;
using System.Security.Cryptography;
using System.Text;

[assembly: AssemblyTitle("Droid Studio")]
[assembly: AssemblyProduct("Droid Studio")]
[assembly: AssemblyDescription("Forensische Sicherung von Android-Listen und Blockly-Automatisierung")]
[assembly: AssemblyVersion("2.0.0.0")]
[assembly: AssemblyFileVersion("2.0.0.0")]

static class Launcher
{
    const string PayloadName = "payload.zip";
    const string Marker = ".droid-studio-payload";

    static int Main(string[] args)
    {
        Console.Title = "Droid Studio";
        string exeDir = Path.GetDirectoryName(Assembly.GetExecutingAssembly().Location);
        string appDir = exeDir;
        try
        {
            using (Stream payload = Assembly.GetExecutingAssembly().GetManifestResourceStream(PayloadName))
            {
                if (payload != null)
                {
                    appDir = Path.Combine(exeDir, "Droid Studio");
                    Unpack(payload, exeDir, appDir);
                }
            }
        }
        catch (Exception error)
        {
            Console.WriteLine("Droid Studio konnte nicht entpackt werden: " + error.Message);
            Console.WriteLine("Bitte die Datei in einen beschreibbaren Ordner legen (zum Beispiel Dokumente) und erneut starten.");
            Pause();
            return 1;
        }

        string python = Path.Combine(appDir, "runtime", "python.exe");
        if (!File.Exists(python))
        {
            Console.WriteLine("Die Programmdateien fehlen neben dieser Datei.");
            Console.WriteLine("Bitte die ZIP-Datei vollständig entpacken und Droid Studio.exe im entpackten Ordner starten.");
            Pause();
            return 1;
        }

        var arguments = new StringBuilder("-B " + Quote(Path.Combine(appDir, "app.py")));
        foreach (string arg in args)
            arguments.Append(' ').Append(Quote(arg));
        var start = new ProcessStartInfo(python, arguments.ToString()) { UseShellExecute = false, WorkingDirectory = appDir };
        // Ctrl+C reaches the app in the same console; it shuts down cleanly and this starter follows.
        Console.CancelKeyPress += (sender, e) => e.Cancel = true;
        using (Process app = Process.Start(start))
        {
            app.WaitForExit();
            if (app.ExitCode != 0)
                Pause();
            return app.ExitCode;
        }
    }

    static void Unpack(Stream payload, string exeDir, string appDir)
    {
        string digest;
        using (var sha = SHA256.Create())
            digest = BitConverter.ToString(sha.ComputeHash(payload)).Replace("-", "");
        string marker = Path.Combine(appDir, Marker);
        if (File.Exists(marker) && File.ReadAllText(marker).Trim() == digest)
            return;
        Console.WriteLine("Droid Studio wird eingerichtet (nur beim ersten Start oder nach einem Update) …");
        Console.WriteLine("Ordner: " + appDir);
        payload.Position = 0;
        string root = Path.GetFullPath(exeDir) + Path.DirectorySeparatorChar;
        using (var archive = new ZipArchive(payload, ZipArchiveMode.Read))
        {
            foreach (ZipArchiveEntry entry in archive.Entries)
            {
                string target = Path.GetFullPath(Path.Combine(exeDir, entry.FullName));
                if (!target.StartsWith(root, StringComparison.OrdinalIgnoreCase))
                    throw new InvalidDataException("Ungültiger Pfad im Paket: " + entry.FullName);
                if (entry.FullName.EndsWith("/"))
                {
                    Directory.CreateDirectory(target);
                    continue;
                }
                Directory.CreateDirectory(Path.GetDirectoryName(target));
                entry.ExtractToFile(target, true);
            }
        }
        File.WriteAllText(marker, digest);
    }

    static string Quote(string value)
    {
        if (value.Length > 0 && value.IndexOfAny(new[] { ' ', '\t', '"' }) < 0)
            return value;
        var quoted = new StringBuilder("\"");
        int backslashes = 0;
        foreach (char c in value)
        {
            if (c == '\\') { backslashes++; continue; }
            if (c == '"') quoted.Append('\\', backslashes * 2 + 1);
            else quoted.Append('\\', backslashes);
            backslashes = 0;
            quoted.Append(c);
        }
        quoted.Append('\\', backslashes * 2).Append('"');
        return quoted.ToString();
    }

    static void Pause()
    {
        Console.WriteLine();
        Console.WriteLine("Zum Schließen eine Taste drücken …");
        try { Console.ReadKey(true); } catch (InvalidOperationException) { }
    }
}
