import React, { useState, useEffect, useRef } from 'react';
import { 
  Search, 
  Film, 
  Clock, 
  CheckCircle2, 
  AlertTriangle, 
  RefreshCw, 
  Cpu, 
  Database, 
  Eye, 
  Play, 
  HelpCircle 
} from 'lucide-react';

const API_BASE_URL = 'http://localhost:8000';

const PIPELINE_STAGES = [
  { key: 'queued', label: 'Job enqueued in background Celery worker' },
  { key: 'metadata', label: 'Retrieving video metadata and duration' },
  { key: 'download', label: 'Downloading media payload and extracting audio' },
  { key: 'transcribe', label: 'Transcribing audio utilizing Whisper model' },
  { key: 'match', label: 'Fuzzy matching target phrase alignment' },
  { key: 'frame', label: 'Rendering target video frame image' }
];

function App() {
  const [link, setLink] = useState('');
  const [phrase, setPhrase] = useState('');
  const [jobId, setJobId] = useState(null);
  const [status, setStatus] = useState(null); // null, 'queued', 'processing', 'completed', 'failed'
  const [errorMsg, setErrorMsg] = useState('');
  const [errorCode, setErrorCode] = useState('');
  const [result, setResult] = useState(null);
  
  const isProcessing = status === 'queued' || status === 'processing';
  
  // Ref for simulated stages timing
  const [activeStageIndex, setActiveStageIndex] = useState(0);
  const timerRef = useRef(null);
  const pollIntervalRef = useRef(null);

  // Submit Job
  const handleSubmit = async (e) => {
    e.preventDefault();
    if (isProcessing) return;
    if (!link.trim() || !phrase.trim()) return;

    // Reset previous states
    setStatus('queued');
    setJobId(null);
    setErrorMsg('');
    setErrorCode('');
    setResult(null);
    setActiveStageIndex(0);

    try {
      const response = await fetch(`${API_BASE_URL}/jobs`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ link, phrase })
      });

      if (!response.ok) {
        throw new Error('Failed to submit job. Backend server may be offline.');
      }

      const data = await response.json();
      setJobId(data.job_id);
      setStatus(data.status); // 'queued'
    } catch (err) {
      setStatus('failed');
      setErrorCode('CONNECTION_ERROR');
      setErrorMsg(err.message || 'Server connection failed.');
    }
  };

  // Simulated Stage Progression for high-fidelity visual feedback
  useEffect(() => {
    if (status === 'queued' || status === 'processing') {
      // Start simulator intervals to slide through pipeline phases
      timerRef.current = setInterval(() => {
        setActiveStageIndex((prevIndex) => {
          if (prevIndex < PIPELINE_STAGES.length - 1) {
            return prevIndex + 1;
          }
          return prevIndex;
        });
      }, 5000); // Progress stage every 5 seconds
    } else {
      clearInterval(timerRef.current);
    }

    return () => clearInterval(timerRef.current);
  }, [status]);

  // Polling Job Status
  useEffect(() => {
    if (!jobId) return;

    const pollJob = async () => {
      try {
        const response = await fetch(`${API_BASE_URL}/jobs/${jobId}`);
        if (!response.ok) return;

        const data = await response.json();
        
        if (data.status === 'completed') {
          setStatus('completed');
          setResult(data.result);
          clearInterval(pollIntervalRef.current);
        } else if (data.status === 'failed') {
          setStatus('failed');
          setErrorCode(data.error_code || 'INTERNAL_ERROR');
          setErrorMsg(data.error || 'Pipeline execution failed.');
          clearInterval(pollIntervalRef.current);
        } else if (data.status === 'processing' && status !== 'processing') {
          setStatus('processing');
        }
      } catch (err) {
        // Suppress connection glitches during polling, keep trying
        console.warn('Polling connection glitch:', err);
      }
    };

    // Run poll immediately, then every 2 seconds
    pollJob();
    pollIntervalRef.current = setInterval(pollJob, 2000);

    return () => clearInterval(pollIntervalRef.current);
  }, [jobId]);

  // Reset Application State
  const handleReset = () => {
    setLink('');
    setPhrase('');
    setJobId(null);
    setStatus(null);
    setErrorMsg('');
    setErrorCode('');
    setResult(null);
    setActiveStageIndex(0);
  };

  // Helper to map backend error codes to descriptive descriptions
  const getErrorDescription = (code) => {
    switch (code) {
      case 'INVALID_OR_UNSUPPORTED_URL':
        return 'The provided video URL is invalid, empty, or points to an unsupported hosting platform.';
      case 'VIDEO_UNAVAILABLE':
        return 'The request video file could not be accessed. It might be private, deleted, or geo-restricted.';
      case 'RATE_LIMIT_OR_BLOCKED':
        return 'The target video hosting server rejected the connection due to rate-limiting or firewall bot blocking.';
      case 'SSL_VERIFICATION_FAILED':
        return 'The local python issuer certificate verification failed when requesting HTTPS handshake from the video website.';
      case 'PHRASE_NOT_FOUND':
        return 'The target search phrase could not be found anywhere within the parsed video audio transcript segments.';
      case 'CONNECTION_ERROR':
        return 'The frontend could not establish a connection to the FastAPI backend API server.';
      default:
        return 'An unexpected server-side execution error occurred in the Celery background pipeline.';
    }
  };

  return (
    <div className="app-container">
      {/* Header Banner */}
      <header style={{ marginBottom: '48px', textAlign: 'center' }}>
        <h1 style={{ fontSize: '3rem', marginBottom: '8px' }}>
          Video <span className="yellow-text">Search & Matcher</span>
        </h1>
      </header>

      {/* Main Grid Layout */}
      <main style={{ maxWidth: '540px', margin: '0 auto' }}>
        
        {/* Form Container (Always Visible) */}
        <div className="flat-panel">
          <h2 style={{ fontSize: '1.5rem', marginBottom: '24px', textAlign: 'left' }}>Submit Search Job</h2>
          <form onSubmit={handleSubmit}>
            <div className="form-group">
              <label className="form-label">Video URL</label>
              <input 
                type="url" 
                className="form-input" 
                placeholder="https://www.youtube.com/watch?v=..."
                value={link}
                onChange={(e) => setLink(e.target.value)}
                disabled={isProcessing}
                required 
              />
            </div>

            <div className="form-group">
              <label className="form-label">Target Phrase to Match</label>
              <input 
                type="text" 
                className="form-input" 
                placeholder="e.g. good morning"
                value={phrase}
                onChange={(e) => setPhrase(e.target.value)}
                disabled={isProcessing}
                required 
              />
            </div>

            <button type="submit" className="btn-primary" style={{ width: '100%', marginTop: '8px' }} disabled={isProcessing}>
              {isProcessing ? (
                <>
                  <RefreshCw size={18} style={{ animation: 'spin 3s linear infinite' }} />
                  Processing Pipeline...
                </>
              ) : (
                <>
                  <Search size={18} />
                  Match Phrase & Extract Frame
                </>
              )}
            </button>
          </form>
        </div>



        {/* Success Results Container */}
        {status === 'completed' && result && (
          <div className="flat-panel">
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '24px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                <CheckCircle2 size={24} style={{ color: 'hsl(var(--color-success))' }} />
                <h2 style={{ margin: 0 }}>Matching Result Found</h2>
              </div>
              <span className="badge">Success</span>
            </div>

            <div className="flat-panel-subtle" style={{ textAlign: 'left', marginBottom: '24px' }}>
              <p style={{ fontSize: '0.75rem', textTransform: 'uppercase', letterSpacing: '0.05em', color: 'hsl(var(--color-text-secondary))', marginBottom: '6px' }}>Matched Phrase segment</p>
              <p style={{ fontSize: '1.25rem', fontWeight: '500', fontStyle: 'italic', color: 'hsl(var(--color-text-primary))', marginBottom: '16px' }}>
                "{result.text}"
              </p>
              
              <div style={{ display: 'flex', gap: '24px', borderTop: '1px solid hsl(var(--color-border))', paddingTop: '16px' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <Clock size={16} style={{ color: 'hsl(var(--color-yellow))' }} />
                  <span style={{ fontSize: '0.875rem' }}>
                    Time: <strong style={{ fontFamily: 'var(--font-mono)' }}>{result.timestamp}</strong>
                  </span>
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <Film size={16} style={{ color: 'hsl(var(--color-yellow))' }} />
                  <span style={{ fontSize: '0.875rem' }}>
                    Frame: <strong>#{result.frame_number}</strong>
                  </span>
                </div>
              </div>
            </div>

            {/* Extracted Frame Image Rendering */}
            <div style={{ textAlign: 'left' }}>
              <p style={{ fontSize: '0.75rem', textTransform: 'uppercase', letterSpacing: '0.05em', color: 'hsl(var(--color-text-secondary))', marginBottom: '8px' }}>Extracted Video Frame</p>
              {result.frame ? (
                <div className="image-preview-container">
                  <img 
                    src={`data:image/jpeg;base64,${result.frame}`} 
                    alt="Matching Video Frame" 
                    className="image-preview" 
                  />
                </div>
              ) : (
                <div className="flat-panel-subtle" style={{ display: 'flex', gap: '12px', alignItems: 'center', justifyContent: 'center', borderStyle: 'dashed' }}>
                  <Eye size={18} style={{ color: 'hsl(var(--color-error))' }} />
                  <span style={{ fontSize: '0.875rem', color: 'hsl(var(--color-text-secondary))' }}>
                    No base64 frame payload returned in job result.
                  </span>
                </div>
              )}
            </div>
          </div>
        )}

        {/* Failure / Error Container */}
        {status === 'failed' && (
          <div className="flat-panel">
            <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '24px' }}>
              <AlertTriangle size={24} style={{ color: 'hsl(var(--color-error))' }} />
              <h2 style={{ margin: 0 }}>Job Execution Failed</h2>
            </div>

            <div className="alert-card error" style={{ marginBottom: '24px' }}>
              <div>
                <p className="alert-title">Error Code: {errorCode}</p>
                <p className="alert-desc">{errorMsg}</p>
              </div>
            </div>

            <div className="flat-panel-subtle" style={{ textAlign: 'left' }}>
              <h3 style={{ fontSize: '0.9375rem', marginBottom: '8px', color: 'hsl(var(--color-text-primary))' }}>What does this mean?</h3>
              <p style={{ fontSize: '0.875rem', color: 'hsl(var(--color-text-secondary))' }}>
                {getErrorDescription(errorCode)}
              </p>
            </div>
          </div>
        )}

      </main>

      {/* Standard CSS animations */}
      <style>{`
        @keyframes spin {
          from { transform: rotate(0deg); }
          to { transform: rotate(360deg); }
        }
      `}</style>
    </div>
  );
}

export default App;
