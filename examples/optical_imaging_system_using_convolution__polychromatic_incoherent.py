import diffractsim
diffractsim.set_backend("CUDA")

from diffractsim import PolychromaticField, ApertureFromImage, cf, mm, cm

def propagate_to_image_plane(F, radius, zi, z0):
    from diffractsim.util.backend_functions import backend as bd
    import numpy as np
    from scipy.interpolate import interp2d
    from pathlib import Path
    from PIL import Image
    import time
    import progressbar

    """
    zi: distance from the image plane to the lens
    z0: distance from the lens the current position
    zi and z0 should satisfy the equation 1/zi + 1/z0 = 1/f 
    where f is the focal distance of the lens
    radius: radius of the lens pupil
    """
    F.z += zi + z0


    if bd != np:
        F.E = F.E.get()

    #magnification factor
    M = zi/z0
    fun = interp2d(
                F.extent_x*(np.arange(F.Nx)-F.Nx//2)/F.Nx,
                F.extent_y*(np.arange(F.Ny)-F.Ny//2)/F.Ny,
                F.E,
                kind="cubic",)
    
    F.E = fun(F.extent_x*(np.arange(F.Nx)-F.Nx//2)/F.Nx/M, 
               F.extent_y*(np.arange(F.Ny)-F.Ny//2)/F.Ny/M )/M
    F.E = bd.array(np.flip(F.E))

    for j in range(len(F.optical_elements)):
        F.E = F.E * F.optical_elements[j].get_transmittance(F.xx, F.yy, 0)


    Ip = F.E * np.conjugate(F.E)
    
    fft_c = bd.fft.fft2(Ip)
    c = bd.fft.fftshift(fft_c)

    fx = bd.fft.fftshift(bd.fft.fftfreq(F.Nx, d = F.x[1]-F.x[0]))
    fy = bd.fft.fftshift(bd.fft.fftfreq(F.Ny, d = F.y[1]-F.y[0]))
    fx, fy = bd.meshgrid(fx, fy)
    fp = bd.sqrt(fx**2 + fy**2)

    bar = progressbar.ProgressBar()

    # We compute the pattern of each wavelength separately, and associate it to small spectrum interval dλ = (780- 380)/spectrum_divisions . We approximately the final colour
    # by summing the contribution of each small spectrum interval converting its intensity distribution to a RGB space.
    
    sRGB_linear = bd.zeros((3, F.Nx * F.Ny))

    t0 = time.time()

    for i in bar(range(F.spectrum_divisions)):
        #Definte the OTF function, representing the Fourier transform of the circular pupil function.

        fc = radius / (F.λ_list_samples[i]* nm  * zi) # coherent cutoff frequency
        H = bd.where(fp < 2 * fc, 2/bd.pi * (bd.arccos(fp / (2*fc)) - fp / (2*fc) * bd.sqrt(1 - (fp / (2*fc))**2)) , bd.zeros_like(fp))
        Iλ = bd.abs(bd.fft.ifft2(bd.fft.ifftshift(c*H)))

        XYZ = F.cs.spec_partition_to_XYZ(bd.outer(Iλ, F.spec_partitions[i]),i)
        sRGB_linear += F.cs.XYZ_to_sRGB_linear(XYZ)

    if bd != np:
        bd.cuda.Stream.null.synchronize()


    rgb = F.cs.sRGB_linear_to_sRGB(sRGB_linear)
    rgb = (rgb.T).reshape((F.Ny, F.Nx, 3))
    print ("Computation Took", time.time() - t0)
    return rgb




from diffractsim import MonochromaticField, nm, mm, cm

f = 1




F = PolychromaticField(
    spectrum=2 * cf.illuminant_d65, extent_x=f * 1.5 * mm, extent_y=f * 1.5 * mm, Nx=2048, Ny=2048,
    spectrum_size = 180, spectrum_divisions = 30
)


F.add(ApertureFromImage( "./apertures/horse.png",  image_size=(f *1.0 * mm, f *1.0 * mm), simulation = F))

rgb = propagate_to_image_plane(F,radius = 5*mm, zi = 50*cm, z0 = 50*cm)

F.plot_colors(rgb, figsize=(5, 5), xlim=[-f*0.4*mm,f*0.4*mm], ylim=[-f*0.4*mm,f*0.4*mm])
