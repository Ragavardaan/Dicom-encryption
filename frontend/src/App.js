import React from 'react';
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import HomePage from './pages/HomePage';
import DicomPage from './pages/DicomPage';

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/"      element={<HomePage />} />
        <Route path="/dicom" element={<DicomPage />} />
      </Routes>
    </BrowserRouter>
  );
}