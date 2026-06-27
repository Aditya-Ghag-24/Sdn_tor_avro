import subprocess
import csv
import time

# Configuration
CSV_FILE = "tor_performance_data.csv"
TRIALS = 6

def get_metrics():
    # Robust Perl script to perform SOCKS5 + HTTP request
    # No extra escaping - passed directly to subprocess
    perl_script = """
use IO::Socket;
my $t0 = time();
my $sock = IO::Socket::INET->new(PeerAddr => "172.18.0.10", PeerPort => 9050, Timeout => 20);
if (!$sock) { print "FAIL_SOCKET"; exit; }

# SOCKS5 Hello
print $sock pack("C3", 0x05, 0x01, 0x00);
read($sock, my $buf, 2);

# SOCKS5 Connect to HSDir DirPort (9030)
# This targets the actual Tor Directory Port for a real download test
print $sock pack("C4Nn", 0x05, 0x01, 0x00, 0x01, unpack("N", pack("C4", 172, 18, 0, 5)), 9030);
read($sock, $buf, 10);
my $t1 = time();

# Fetch the consensus (~1.5MB file)
print $sock "GET /tor/status-vote/current/consensus HTTP/1.0\\r\\nHost: 172.18.0.5\\r\\n\\r\\n";
my $received = 0;
while (read($sock, my $data, 16384)) { 
    $received += length($data); 
}
my $t2 = time();
printf("%d,%d,%d", $t1 - $t0, $received, $t2 - $t0);
"""
    # Using list to avoid shell interpretation errors
    docker_cmd = ["docker", "exec", "mn.tor_cli", "perl", "-e", perl_script]
    
    try:
        result = subprocess.check_output(docker_cmd, stderr=subprocess.STDOUT).decode('utf-8').strip()
        if "FAIL" in result or not result or ',' not in result:
            return None, None
            
        ttfb, received, total = result.split(',')
        
        # Calculate speed in Mbps (received * 8 / total / 1,000,000)
        # If total time is 0 (very fast), we assume 0.5s for the calculation
        time_denom = float(total) if float(total) > 0 else 0.5
        speed_mbps = (float(received) * 8) / (time_denom * 1_000_000)
        
        return float(ttfb), speed_mbps
    except Exception:
        return None, None

def main():
    results = []
    print(f"Starting {TRIALS} trials for AVRO Performance Measurement...")
    print("Target: HSDir Consensus (via Tor 3-hop circuit)\n")

    for i in range(TRIALS):
        ttfb, speed = get_metrics()
        if ttfb is not None and speed > 0:
            results.append({'trial': i+1, 'ttfb': ttfb, 'throughput_mbps': speed})
            print(f"Trial {i+1}: TTFB={ttfb:.0f}s, Throughput={speed:.2f} Mbps")
        else:
            print(f"Trial {i+1}: FAILED (Circuit building or SDN path optimization in progress...)")
        time.sleep(4)

    if results:
        avg_ttfb = sum(r['ttfb'] for r in results) / len(results)
        avg_speed = sum(r['throughput_mbps'] for r in results) / len(results)

        with open(CSV_FILE, mode='w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=['trial', 'ttfb', 'throughput_mbps'])
            writer.writeheader()
            writer.writerows(results)
            writer.writerow({'trial': 'AVERAGE', 'ttfb': avg_ttfb, 'throughput_mbps': avg_speed})

        print(f"\nSuccess! Data saved to {CSV_FILE}")
        print(f"Average TTFB (Latency): {avg_ttfb:.2f}s")
        print(f"Average Throughput: {avg_speed:.2f} Mbps")
    else:
        print("\nNo data collected. Ensure 'tor_cli' is at 100% Bootstrap before running.")

if __name__ == "__main__":
    main()
