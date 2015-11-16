# -*- coding: utf-8 -*-
import ROOT
import AbstractClasses
import AbstractClasses.Helper.HistoGetter as HistoGetter
import array

class TestResult(AbstractClasses.GeneralTestResult.GeneralTestResult):
    def CustomInit(self):
        self.NameSingle = 'DoubleColumnEfficiencyDistribution'
        self.Name = 'CMSPixel_QualificationGroup_XRayHRQualification_Chips_Chip_%s_TestResult'%self.NameSingle
        self.Attributes['TestedObjectType'] = 'CMSPixel_QualificationGroup_XRayHRQualification_ROC'
        self.ResultData['KeyValueDictPairs'] = {}
        
        
    def PopulateResultData(self):
        self.Canvas.Clear()

        ChipNo = self.ParentObject.Attributes['ChipNo']
        Rates = self.ParentObject.ParentObject.ParentObject.Attributes['Rates']
        PixelArea = 150 * 100 * 1.e-8
        RealHitrateList = array.array('d', [0])
        EfficiencyList = array.array('d', [100])
        ScalingFactor = 1e-6

        BAD_DOUBLECOLUMN_DATA = 1
        BAD_DOUBLECOLUMN_FIT = 2
        BAD_DOUBLECOLUMN_BADPIX = 3

        # calculate efficiencies for all rates
        DoubleColumnEfficiencies = []
        BadDoubleColumns = []
        for InterpolationRate in self.ParentObject.ParentObject.ParentObject.Attributes['InterpolatedEfficiencyRates']:
            DoubleColumnEfficienciesRate = []

            # and all double columns
            for DoubleColumn in range(0, 26):
                DoubleColumnRateList = array.array('d')
                DoubleColumnEfficiencyList = array.array('d')

                for Rate in Rates['HREfficiency']:
                    Ntrig = self.ParentObject.ParentObject.ParentObject.Attributes['Ntrig']['HREfficiency_{Rate}'.format(Rate=Rate)]
                    EfficiencyMapROOTObject = self.ParentObject.ResultData['SubTestResults']['EfficiencyMap_{Rate}'.format(Rate=Rate)].ResultData['Plot']['ROOTObject']
                    BackgroundMapROOTObject = self.ParentObject.ResultData['SubTestResults']['BackgroundMap_{Rate}'.format(Rate=Rate)].ResultData['Plot']['ROOTObject']

                    PixelRateList = array.array('d')
                    PixelEfficiencyList = array.array('d')
                    BadPixelsList = []

                    PixelEfficiencyMean = EfficiencyMapROOTObject.GetMean()
                    PixelEfficiencyRMS = EfficiencyMapROOTObject.GetRMS()
                    PixelEfficiencyThreshold = min(self.TestResultEnvironmentObject.GradingParameters['XRayHighRateEfficiency_max_bad_pixels_cut_max'], max(self.TestResultEnvironmentObject.GradingParameters['XRayHighRateEfficiency_max_bad_pixels_cut_min'], PixelEfficiencyMean - self.TestResultEnvironmentObject.GradingParameters['XRayHighRateEfficiency_max_bad_pixels_cut_sigma'] * PixelEfficiencyRMS))
                    MaximumNumberAllowedBadPixels = self.TestResultEnvironmentObject.GradingParameters['XRayHighRateEfficiency_max_bad_pixels_per_double_column']

                    for PixNo in range(0, 160):
                        col = DoubleColumn * 2 + (1 if PixNo > 79 else 0)
                        row = PixNo % 80
                        PixelNHits = EfficiencyMapROOTObject.GetBinContent(col + 1, row + 1)
                        BackgroundMapNHits = BackgroundMapROOTObject.GetBinContent(col + 1, row + 1)

                        # only count alive pixels
                        if PixelNHits > 0:
                            PixelEfficiency = PixelNHits/Ntrig
                            AreaFactor = 1 * (2 if col==0 or col==51 else 1) * (2 if row==0 or row==79 else 1)

                            if PixelEfficiency < PixelEfficiencyThreshold:
                                BadPixelsList.append([PixNo])

                            # in MHz/cm2
                            PixelRate = BackgroundMapNHits / (25 * 1e-9 * Ntrig * 4160 * PixelArea * AreaFactor) * ScalingFactor

                            PixelRateList.append(PixelRate)
                            PixelEfficiencyList.append(PixelEfficiency)

                    # if more than X pixel with very(!) bad efficiency in double column, declare DC as bad
                    if len(BadPixelsList) > MaximumNumberAllowedBadPixels:
                        BadDoubleColumns.append({'Chip': ChipNo, 'DoubleColumn': DoubleColumn, 'Error': BAD_DOUBLECOLUMN_BADPIX})

                    try:
                        DoubleColumnMeanEfficiency = ROOT.TMath.Mean(len(PixelEfficiencyList), PixelEfficiencyList)
                        DoubleColumnRate = ROOT.TMath.Mean(len(PixelRateList), PixelRateList)
                        # correct measured hit rate by efficiency, in %
                        DoubleColumnRateList.append(DoubleColumnRate / DoubleColumnMeanEfficiency)
                        DoubleColumnMeanEfficiencyPercent = DoubleColumnMeanEfficiency * 100
                        DoubleColumnEfficiencyList.append(DoubleColumnMeanEfficiencyPercent)
                    except:
                        BadDoubleColumns.append({'Chip': ChipNo, 'DoubleColumn': DoubleColumn, 'Error': BAD_DOUBLECOLUMN_DATA})

                try:
                    cubicFit = ROOT.TF1("fitfunction", "[0]-[1]*x^3", 5, 200)
                    cubicFit.SetParameter(1, 100)
                    cubicFit.SetParameter(2, 5e-7)

                    EfficiencyGraph = ROOT.TGraph(len(DoubleColumnRateList), DoubleColumnRateList, DoubleColumnEfficiencyList)
                    EfficiencyGraph.Fit(cubicFit, 'QR')
                    InterpolatedEfficiency = cubicFit.Eval(InterpolationRate * 1.0e6 * ScalingFactor)

                    DoubleColumnEfficienciesRate.append(InterpolatedEfficiency)
                    cubicFit.Delete()
                    EfficiencyGraph.Delete()
                except:
                    BadDoubleColumns.append({'Chip': ChipNo, 'DoubleColumn': DoubleColumn, 'Error': BAD_DOUBLECOLUMN_FIT})

            DoubleColumnEfficiencies.append(DoubleColumnEfficienciesRate)

        
        # get minimum efficiency
        AllDoubleColumnEfficiencies = [item for sublist in DoubleColumnEfficiencies for item in sublist]
        EfficiencyMinimum = min(95, min(AllDoubleColumnEfficiencies))

        # draw histogram for each of the different rates with different color
        RootHistograms = []
        First = True
        CurveColors = [ROOT.kBlue+2,ROOT.kRed+1, ROOT.kGreen+3]
        ColorIndex = 0
        for DoubleColumnEfficienciesRate in DoubleColumnEfficiencies:
            RootHistogram = ROOT.TH1D(self.GetUniqueID(), '', 1000, 0, 100)
            RootHistogram.GetXaxis().SetRangeUser(EfficiencyMinimum, 100)

            for DoubleColumnEfficiency in DoubleColumnEfficienciesRate:
                RootHistogram.Fill(DoubleColumnEfficiency)

            if RootHistogram:
                    RootHistogram.SetLineColor(CurveColors[ColorIndex])
                    ColorIndex += 1
                    if ColorIndex > len(CurveColors)-1:
                        ColorIndex = 0
                    if First:
                        RootHistogram.Draw("")
                        First = False
                    else:
                        RootHistogram.Draw("same")
                    RootHistograms.append(RootHistogram)

        Legend = ROOT.TLegend(0.2,0.85,0.4,0.65)
        for i in range(len(RootHistograms)):
            Legend.AddEntry(RootHistograms[i], '%d MHz/cm2'%self.ParentObject.ParentObject.ParentObject.Attributes['InterpolatedEfficiencyRates'][i], 'l')
        Legend.Draw("")
        ROOT.gPad.Update()

        self.Title = 'DC Efficiency Distribution: C{ChipNo}'.format(ChipNo=self.ParentObject.Attributes['ChipNo'])
        self.SaveCanvas()

        self.ResultData['HiddenData']['BadDoubleColumns'] = BadDoubleColumns
        self.ResultData['KeyValueDictPairs']['NBadDoubleColumns'] = {'Label': 'Bad Double Columns', 'Value': len(set([BadDoubleColumn['DoubleColumn'] for BadDoubleColumn in BadDoubleColumns]))}
        self.ResultData['KeyList'].append('NBadDoubleColumns')

        try:
            for i in RootHistograms:
                i.Delete()
        except:
            pass


