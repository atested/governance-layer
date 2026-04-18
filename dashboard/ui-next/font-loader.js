// Promote font stylesheet from print to all on load (CSP-safe alternative to inline onload).
document.getElementById('font-sheet').addEventListener('load', function() { this.media = 'all'; });
