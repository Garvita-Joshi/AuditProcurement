import React, { useRef, useState } from 'react';
import { UploadCloud, File as FileIcon, X, CheckCircle, AlertCircle } from 'lucide-react';
import './FileUpload.css';

export default function FileUpload({ onUpload, accept, label, multiple = false, uploadState = 'idle' }) {
  const fileInputRef = useRef(null);
  const [dragActive, setDragActive] = useState(false);
  const [selectedFiles, setSelectedFiles] = useState([]);

  const handleDrag = (e) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === "dragenter" || e.type === "dragover") {
      setDragActive(true);
    } else if (e.type === "dragleave") {
      setDragActive(false);
    }
  };

  const handleDrop = (e) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      handleFiles(e.dataTransfer.files);
    }
  };

  const handleChange = (e) => {
    e.preventDefault();
    if (e.target.files && e.target.files[0]) {
      handleFiles(e.target.files);
    }
  };

  const handleFiles = (files) => {
    const filesArray = Array.from(files);
    setSelectedFiles(multiple ? filesArray : [filesArray[0]]);
  };

  const removeFile = (index) => {
    const newFiles = [...selectedFiles];
    newFiles.splice(index, 1);
    setSelectedFiles(newFiles);
  };

  const handleUploadClick = () => {
    if (selectedFiles.length > 0) {
      onUpload(multiple ? selectedFiles : selectedFiles[0]);
    }
  };

  return (
    <div className="file-upload-wrapper">
      {uploadState === 'idle' || uploadState === 'error' ? (
        <>
          <div 
            className={`dropzone ${dragActive ? "active" : ""}`}
            onDragEnter={handleDrag}
            onDragLeave={handleDrag}
            onDragOver={handleDrag}
            onDrop={handleDrop}
            onClick={() => fileInputRef.current.click()}
          >
            <input 
              ref={fileInputRef}
              type="file"
              accept={accept}
              multiple={multiple}
              onChange={handleChange}
              style={{ display: "none" }}
            />
            
            <UploadCloud size={48} className="dropzone-icon mb-4" />
            <p className="text-lg font-medium mb-1">{label}</p>
            <p className="text-sm text-secondary">Drag and drop or click to select</p>
          </div>

          {selectedFiles.length > 0 && (
            <div className="selected-files mt-4">
              {selectedFiles.map((file, i) => (
                <div key={i} className="file-item">
                  <div className="flex items-center gap-3">
                    <FileIcon size={20} className="text-accent-primary" />
                    <span className="file-name">{file.name}</span>
                  </div>
                  <button onClick={() => removeFile(i)} className="text-muted hover:text-danger">
                    <X size={16} />
                  </button>
                </div>
              ))}
              
              <button 
                className="btn btn-primary mt-4 w-full"
                onClick={handleUploadClick}
              >
                Upload {selectedFiles.length} file{selectedFiles.length > 1 ? 's' : ''}
              </button>
            </div>
          )}
        </>
      ) : uploadState === 'uploading' || uploadState === 'processing' ? (
        <div className="upload-progress glass-card text-center py-12">
          <div className="spinner mb-4 mx-auto"></div>
          <h3 className="text-xl font-medium">Processing...</h3>
          <p className="text-secondary mt-2">This may take a moment</p>
        </div>
      ) : (
        <div className="upload-success glass-card text-center py-12">
          <CheckCircle size={48} className="text-status-success mx-auto mb-4" />
          <h3 className="text-xl font-medium">Upload Complete</h3>
          <button className="btn btn-secondary mt-6" onClick={() => setSelectedFiles([])}>
            Upload Another
          </button>
        </div>
      )}
    </div>
  );
}
